"""Topolyx .tlyx 파일을 읽어 파이썬 객체로 복원한다."""

import json
from pathlib import Path
from typing import Tuple

from . import topolyx_validator
from .topolyx_binary import read_tlyx_container
from .topolyx_types import TopolyxFile


def read_topolyx(filepath: str | Path) -> Tuple[TopolyxFile, bytes]:
    """Topolyx .tlyx 파일을 읽어 검증하고 TopolyxFile 객체와 binary 데이터를 반환한다.

    Args:
        filepath: .tlyx 파일 경로.

    Returns:
        (topolyx_file, bin_data): 파싱된 TopolyxFile 객체와 raw binary bytes.

    Raises:
        topolyx_validator.TopolyxValidationError: 파일이 명세 조건을 만족하지 않을 경우.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Topolyx file not found: {path}")

    container_data = path.read_bytes()
    json_bytes, bin_data = read_tlyx_container(container_data)
    json_data = json.loads(json_bytes.decode("utf-8"))

    topolyx_validator.validate_topolyx(json_data, bin_data)

    return TopolyxFile.from_dict(json_data), bin_data


def read_topolyx_from_data(json_data: dict, bin_data: bytes) -> TopolyxFile:
    """이미 로드된 JSON dict와 binary bytes에서 TopolyxFile 객체를 생성한다.

    읽기 전 validate_topolyx()를 호출하여 명세 조건을 만족하는지 검증한다.
    """
    topolyx_validator.validate_topolyx(json_data, bin_data)
    return TopolyxFile.from_dict(json_data)
