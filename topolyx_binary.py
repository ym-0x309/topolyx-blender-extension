"""Topolyx binary buffer 작성/읽기 유틸리티."""

import array
import struct
from pathlib import Path
from typing import Iterable, Sequence


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
        buf = values if isinstance(values, array.array) else array.array("f", values)
        self._data.extend(buf.tobytes())
        return offset

    def append_i32(self, values: Sequence[int]) -> int:
        """I32 배열을 추가하고 시작 byte offset을 반환한다."""
        self._align(4)
        offset = len(self._data)
        buf = values if isinstance(values, array.array) else array.array("i", values)
        self._data.extend(buf.tobytes())
        return offset

    def append_u32(self, values: Sequence[int]) -> int:
        """U32 배열을 추가하고 시작 byte offset을 반환한다."""
        self._align(4)
        offset = len(self._data)
        buf = values if isinstance(values, array.array) else array.array("I", values)
        self._data.extend(buf.tobytes())
        return offset

    def append_i8(self, values: Sequence[int]) -> int:
        """I8 배열을 1바이트씩 추가하고 시작 byte offset을 반환한다."""
        self._align(4)
        offset = len(self._data)
        buf = values if isinstance(values, array.array) else array.array("b", values)
        self._data.extend(buf.tobytes())
        return offset

    def append_u8(self, values: Sequence[int]) -> int:
        """U8 배열을 1바이트씩 추가하고 시작 byte offset을 반환한다."""
        self._align(4)
        offset = len(self._data)
        buf = values if isinstance(values, array.array) else array.array("B", values)
        self._data.extend(buf.tobytes())
        return offset

    def append_bool(self, values: Iterable[int]) -> int:
        """BOOL 배열을 1바이트씩 추가하고 시작 byte offset을 반환한다.

        값은 0 또는 1이어야 하며, 그 외 값은 validator에서 거부된다.
        """
        self._align(4)
        offset = len(self._data)
        self._data.extend(bytes(1 if v else 0 for v in values))
        return offset

    def byte_length(self) -> int:
        """현재 버퍼의 총 byte 길이를 반환한다."""
        return len(self._data)

    def to_bytes(self) -> bytes:
        """버퍼 내용을 bytes로 반환한다."""
        return bytes(self._data)

    def write(self, path: Path) -> None:
        """버퍼 내용을 지정한 경로에 쓴다."""
        with open(path, "wb") as f:
            f.write(self._data)


class BinaryBufferReader:
    """4바이트 정렬된 little-endian scalar 배열을 읽는 reader."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def _check_bounds(self, offset: int, length: int) -> None:
        """읽으려는 범위가 버퍼 안에 있는지 확인한다."""
        if offset < 0:
            raise ValueError(f"offset must be non-negative, got {offset}")
        end = offset + length
        if end > len(self._data):
            raise ValueError(
                f"read out of bounds: {offset} + {length} > {len(self._data)}"
            )

    def read_f32(self, offset: int, count: int) -> array.array:
        """offset 위치부터 count개의 F32 값을 읽어 array.array('f')로 반환한다."""
        if count == 0:
            return array.array("f")
        self._check_bounds(offset, count * 4)
        return array.array("f", self._data[offset : offset + count * 4])

    def read_i32(self, offset: int, count: int) -> array.array:
        """offset 위치부터 count개의 I32 값을 읽어 array.array('i')로 반환한다."""
        if count == 0:
            return array.array("i")
        self._check_bounds(offset, count * 4)
        return array.array("i", self._data[offset : offset + count * 4])

    def read_u32(self, offset: int, count: int) -> array.array:
        """offset 위치부터 count개의 U32 값을 읽어 array.array('I')로 반환한다."""
        if count == 0:
            return array.array("I")
        self._check_bounds(offset, count * 4)
        return array.array("I", self._data[offset : offset + count * 4])

    def read_i8(self, offset: int, count: int) -> array.array:
        """offset 위치부터 count개의 I8 값을 읽어 array.array('b')로 반환한다."""
        if count == 0:
            return array.array("b")
        self._check_bounds(offset, count)
        return array.array("b", self._data[offset : offset + count])

    def read_u8(self, offset: int, count: int) -> array.array:
        """offset 위치부터 count개의 U8 값을 읽어 array.array('B')로 반환한다."""
        if count == 0:
            return array.array("B")
        self._check_bounds(offset, count)
        return array.array("B", self._data[offset : offset + count])

    def read_bool(self, offset: int, count: int) -> array.array:
        """offset 위치부터 count개의 BOOL 값을 읽어 array.array('b')로 반환한다."""
        if count == 0:
            return array.array("b")
        self._check_bounds(offset, count)
        return array.array("b", self._data[offset : offset + count])

    def __len__(self) -> int:
        """버퍼의 총 byte 길이를 반환한다."""
        return len(self._data)
