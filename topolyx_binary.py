"""Topolyx binary buffer 작성/읽기 유틸리티."""

import array
import struct
from pathlib import Path
from typing import Iterable, Sequence, Tuple


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


_TLYX_MAGIC = b"TLYX"
_TLYX_VERSION = 1
_HEADER_SIZE = 12
_CHUNK_HEADER_SIZE = 8


class TopolyxContainerError(Exception):
    """.tlyx 컨테이너 형식이 잘못되었을 때 발생하는 예외."""

    pass


def _pad_json(json_bytes: bytes) -> bytes:
    """JSON 청크 데이터를 4바이트 경계로 0x20(space)로 패딩한다."""
    remainder = len(json_bytes) % 4
    if remainder:
        return json_bytes + b"\x20" * (4 - remainder)
    return json_bytes


def _pad_bin(bin_bytes: bytes) -> bytes:
    """BIN 청크 데이터를 4바이트 경계로 0x00으로 패딩한다."""
    remainder = len(bin_bytes) % 4
    if remainder:
        return bin_bytes + b"\x00" * (4 - remainder)
    return bin_bytes


def write_tlyx_container(json_bytes: bytes, bin_bytes: bytes) -> bytes:
    """JSON 청크와 BIN 청크를 조립하여 .tlyx 컨테이너 bytes를 반환한다.

    Args:
        json_bytes: UTF-8로 인코딩된 JSON 데이터. 4바이트 정렬되지 않아도 된다.
        bin_bytes: 4바이트 정렬되지 않아도 되는 binary 데이터.

    Returns:
        .tlyx 파일의 전체 byte 내용.
    """
    padded_json = _pad_json(json_bytes)
    padded_bin = _pad_bin(bin_bytes)

    json_chunk_length = len(padded_json)
    bin_chunk_length = len(padded_bin)

    total_length = (
        _HEADER_SIZE
        + _CHUNK_HEADER_SIZE
        + json_chunk_length
        + _CHUNK_HEADER_SIZE
        + bin_chunk_length
    )

    header = struct.pack("<4sII", _TLYX_MAGIC, _TLYX_VERSION, total_length)
    json_chunk = struct.pack("<I4s", json_chunk_length, b"JSON") + padded_json
    bin_chunk = struct.pack("<I4s", bin_chunk_length, b"BIN\0") + padded_bin

    return header + json_chunk + bin_chunk


def read_tlyx_container(data: bytes) -> Tuple[bytes, bytes]:
    """.tlyx 컨테이너 bytes를 읽어 JSON 청크와 BIN 청크 데이터를 반환한다.

    Args:
        data: .tlyx 파일의 전체 byte 내용.

    Returns:
        (json_bytes, bin_bytes): 패딩이 제거된 JSON과 BIN 청크 데이터.

    Raises:
        TopolyxContainerError: 컨테이너 형식이 올바르지 않을 경우.
    """
    if len(data) < _HEADER_SIZE:
        raise TopolyxContainerError("File is too short to contain a Topolyx header")

    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != _TLYX_MAGIC:
        raise TopolyxContainerError(f"Invalid magic bytes: {magic!r}")
    if version != _TLYX_VERSION:
        raise TopolyxContainerError(
            f"Unsupported container version: {version} (expected {_TLYX_VERSION})"
        )
    if total_length != len(data):
        raise TopolyxContainerError(
            f"total_length mismatch: {total_length} vs actual {len(data)}"
        )

    offset = _HEADER_SIZE

    if offset + _CHUNK_HEADER_SIZE > len(data):
        raise TopolyxContainerError("JSON chunk header is missing")
    json_chunk_length, json_chunk_type = struct.unpack_from("<I4s", data, offset)
    if json_chunk_type != b"JSON":
        raise TopolyxContainerError(
            f"Expected JSON chunk, got {json_chunk_type!r}"
        )
    if json_chunk_length % 4 != 0:
        raise TopolyxContainerError(
            f"JSON chunk length must be a multiple of 4, got {json_chunk_length}"
        )

    offset += _CHUNK_HEADER_SIZE
    json_end = offset + json_chunk_length
    if json_end > len(data):
        raise TopolyxContainerError("JSON chunk data exceeds file length")
    json_bytes = data[offset:json_end]
    offset = json_end

    if offset + _CHUNK_HEADER_SIZE > len(data):
        raise TopolyxContainerError("BIN chunk header is missing")
    bin_chunk_length, bin_chunk_type = struct.unpack_from("<I4s", data, offset)
    if bin_chunk_type != b"BIN\0":
        raise TopolyxContainerError(
            f"Expected BIN chunk, got {bin_chunk_type!r}"
        )
    if bin_chunk_length % 4 != 0:
        raise TopolyxContainerError(
            f"BIN chunk length must be a multiple of 4, got {bin_chunk_length}"
        )

    offset += _CHUNK_HEADER_SIZE
    bin_end = offset + bin_chunk_length
    if bin_end > len(data):
        raise TopolyxContainerError("BIN chunk data exceeds file length")
    bin_bytes = data[offset:bin_end]

    # JSON 청크 뒤의 패딩 바이트(0x20)와 BIN 청크 뒤의 패딩 바이트(0x00)은 제거하지 않는다.
    # reader는 byte_offset/byte_length로 데이터를 참조하므로, validator가 패딩을 검증한다.
    return json_bytes, bin_bytes
