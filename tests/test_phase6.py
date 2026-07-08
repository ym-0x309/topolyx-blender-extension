"""Phase 6 테스트 — 개선된 공유 유틸리티 및 reader 검증.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase6.py
"""

import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy
from mathutils import Matrix, Vector

from blender_mattr_exporter.mattr_attribute import mattr_component_type_to_blender
from blender_mattr_exporter.mattr_binary import BinaryBuffer, BinaryBufferReader
from blender_mattr_exporter.mattr_coordinate import CoordinateConverter
from blender_mattr_exporter.mattr_reader import read_mattr
from blender_mattr_exporter.mattr_utils import (
    column_major_list_to_matrix,
    matrix_to_column_major_list,
)
from blender_mattr_exporter.tests import common


def test_inverse_coordinate_conversion():
    """CoordinateConverter의 역변환이 정방향 변환을 되돌리는지 확인한다."""
    converter = CoordinateConverter("MATTR_DEFAULT")

    pos = Vector((1.0, 2.0, 3.0))
    converted = converter.convert_position(pos)
    recovered = converter.inverse_convert_position(converted)
    assert (pos - recovered).length < 1e-6

    direction = Vector((0.0, 0.0, 1.0))
    converted_dir = converter.convert_direction(direction)
    recovered_dir = converter.inverse_convert_direction(converted_dir)
    assert (direction - recovered_dir).length < 1e-6

    matrix = Matrix.Translation(Vector((4.0, 5.0, 6.0)))
    converted_matrix = converter.convert_matrix(matrix)
    recovered_matrix = converter.inverse_convert_matrix(converted_matrix)
    assert (matrix.to_translation() - recovered_matrix.to_translation()).length < 1e-6

    print("test_inverse_coordinate_conversion passed")


def test_matrix_serialization_round_trip():
    """행렬 직렬화/역직렬화가 정확한지 확인한다."""
    matrix = Matrix.Translation(Vector((1.0, 2.0, 3.0)))
    column_major = matrix_to_column_major_list(matrix)
    assert len(column_major) == 16
    # column-major에서 translation은 인덱스 12, 13, 14
    assert abs(column_major[12] - 1.0) < 1e-6
    assert abs(column_major[13] - 2.0) < 1e-6
    assert abs(column_major[14] - 3.0) < 1e-6

    recovered = column_major_list_to_matrix(column_major)
    assert (matrix.to_translation() - recovered.to_translation()).length < 1e-6

    print("test_matrix_serialization_round_trip passed")


def test_binary_buffer_reader():
    """BinaryBuffer에 쓴 데이터를 BinaryBufferReader로 정확히 읽는지 확인한다."""
    buffer = BinaryBuffer()
    f32_offset = buffer.append_f32([1.0, 2.0, 3.0, 4.0])
    i32_offset = buffer.append_i32([-1, 0, 1])
    u32_offset = buffer.append_u32([10, 20, 30])

    reader = BinaryBufferReader(buffer.to_bytes())

    f32_values = list(reader.read_f32(f32_offset, 4))
    assert f32_values == [1.0, 2.0, 3.0, 4.0]

    i32_values = list(reader.read_i32(i32_offset, 3))
    assert i32_values == [-1, 0, 1]

    u32_values = list(reader.read_u32(u32_offset, 3))
    assert u32_values == [10, 20, 30]

    print("test_binary_buffer_reader passed")


def test_mattr_component_type_to_blender():
    """MATTR attribute 타입을 Blender 타입으로 올바르게 환산하는지 확인한다."""
    assert mattr_component_type_to_blender("F32", 1) == ("FLOAT", "value")
    assert mattr_component_type_to_blender("F32", 2) == ("FLOAT2", "vector")
    assert mattr_component_type_to_blender("F32", 3) == ("FLOAT_VECTOR", "vector")
    assert mattr_component_type_to_blender("F32", 4) == ("FLOAT_COLOR", "color")
    assert mattr_component_type_to_blender("F32", 4, use_byte_color=True) == (
        "BYTE_COLOR",
        "color",
    )
    assert mattr_component_type_to_blender("I32", 1) == ("INT", "value")
    assert mattr_component_type_to_blender("I32", 2) == ("INT32_2D", "vector")

    try:
        mattr_component_type_to_blender("U32", 1)
        raise AssertionError("Expected ValueError for unsupported U32x1")
    except ValueError:
        pass

    print("test_mattr_component_type_to_blender passed")


def test_read_mattr():
    """mattr_reader가 익스포트한 파일을 올바르게 파싱하는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "reader_cube")
        mattr_file, bin_data = read_mattr(json_path)

        assert mattr_file.header.format == "MATTR"
        assert mattr_file.header.version == "0.1.0"
        assert mattr_file.buffer.byte_length == len(bin_data)
        assert len(mattr_file.objects) == 1
        assert len(mattr_file.meshes) == 1

        mesh = mattr_file.meshes[0]
        assert mesh.element_counts.vertices == 8
        assert mesh.element_counts.edges == 12
        assert mesh.element_counts.faces == 6
        assert mesh.element_counts.corners == 24

        obj = mattr_file.objects[0]
        assert obj.type == "MESH"
        assert obj.index == 0
        assert len(obj.transform) == 16
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_read_mattr passed")


def main():
    common.reset_addon()
    test_inverse_coordinate_conversion()
    test_matrix_serialization_round_trip()
    test_binary_buffer_reader()
    test_mattr_component_type_to_blender()
    test_read_mattr()
    print("All Phase 6 tests passed")


if __name__ == "__main__":
    main()
