"""MATTR binary buffer 작성 유틸리티."""

import struct
from pathlib import Path
from typing import Sequence


class BinaryBuffer:
    """little-endian scalar 배열을 4바이트 정렬로 조립하는 버퍼."""

    def __init__(self) -> None:
        self._data = bytearray()

    def _align(self, alignment: int = 4) -> None:
        """현재 버퍼 길이가 alignment 배수가 되도록 0으로 패딩한다."""
        remainder = len(self._data) % alignment
        if remainder:
            self._data.extend(b"\x00" * (alignment - remainder))

    def append_f32(self, values: Sequence[float]) -> int:
        """F32 배열을 추가하고 시작 byte offset을 반환한다."""
        self._align(4)
        offset = len(self._data)
        self._data.extend(struct.pack(f"<{len(values)}f", *values))
        return offset

    def append_i32(self, values: Sequence[int]) -> int:
        """I32 배열을 추가하고 시작 byte offset을 반환한다."""
        self._align(4)
        offset = len(self._data)
        self._data.extend(struct.pack(f"<{len(values)}i", *values))
        return offset

    def append_u32(self, values: Sequence[int]) -> int:
        """U32 배열을 추가하고 시작 byte offset을 반환한다."""
        self._align(4)
        offset = len(self._data)
        self._data.extend(struct.pack(f"<{len(values)}I", *values))
        return offset

    def byte_length(self) -> int:
        """현재 버퍼의 총 byte 길이를 반환한다."""
        return len(self._data)

    def write(self, path: Path) -> None:
        """버퍼 내용을 지정한 경로에 쓴다."""
        with open(path, "wb") as f:
            f.write(self._data)
