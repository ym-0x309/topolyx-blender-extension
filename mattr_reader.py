"""MATTR JSON + binary 파일을 읽어 파이썬 객체로 복원한다."""

import json
from pathlib import Path
from typing import Tuple

from . import mattr_validator
from .mattr_types import MattrFile


def read_mattr(json_path: str | Path) -> Tuple[MattrFile, bytes]:
    """MATTR 파일 쌍을 읽어 검증하고 MattrFile 객체와 binary 데이터를 반환한다.

    Args:
        json_path: .mattr.json 파일 경로. 같은 basename의 .mattr.bin 파일이
            같은 디렉터리에 있어야 한다.

    Returns:
        (mattr_file, bin_data): 파싱된 MattrFile 객체와 raw binary bytes.

    Raises:
        mattr_validator.MattrValidationError: 파일이 명세 조건을 만족하지 않을 경우.
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

    mattr_validator.validate_mattr(json_data, bin_data)

    return MattrFile.from_dict(json_data), bin_data


def read_mattr_from_data(json_data: dict, bin_data: bytes) -> MattrFile:
    """이미 로드된 JSON dict와 binary bytes에서 MattrFile 객체를 생성한다.

    읽기 전 validate_mattr()를 호출하여 명세 조건을 만족하는지 검증한다.
    """
    mattr_validator.validate_mattr(json_data, bin_data)
    return MattrFile.from_dict(json_data)
