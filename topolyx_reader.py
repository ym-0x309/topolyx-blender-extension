"""Topolyx JSON + binary 파일을 읽어 파이썬 객체로 복원한다."""

import json
from pathlib import Path
from typing import Tuple

from . import topolyx_validator
from .topolyx_types import TopolyxFile


def read_topolyx(json_path: str | Path) -> Tuple[TopolyxFile, bytes]:
    """Topolyx 파일 쌍을 읽어 검증하고 TopolyxFile 객체와 binary 데이터를 반환한다.

    Args:
        json_path: .tlyx.json 파일 경로. 같은 basename의 .tlyx.bin 파일이
            같은 디렉터리에 있어야 한다.

    Returns:
        (topolyx_file, bin_data): 파싱된 TopolyxFile 객체와 raw binary bytes.

    Raises:
        topolyx_validator.TopolyxValidationError: 파일이 명세 조건을 만족하지 않을 경우.
    """
    json_path = Path(json_path)
    bin_path = json_path.with_name(json_path.stem + ".bin")

    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    if not bin_path.exists():
        raise FileNotFoundError(f"Binary file not found: {bin_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    bin_data = bin_path.read_bytes()

    topolyx_validator.validate_topolyx(json_data, bin_data)

    return TopolyxFile.from_dict(json_data), bin_data


def read_topolyx_from_data(json_data: dict, bin_data: bytes) -> TopolyxFile:
    """이미 로드된 JSON dict와 binary bytes에서 TopolyxFile 객체를 생성한다.

    읽기 전 validate_topolyx()를 호출하여 명세 조건을 만족하는지 검증한다.
    """
    topolyx_validator.validate_topolyx(json_data, bin_data)
    return TopolyxFile.from_dict(json_data)
