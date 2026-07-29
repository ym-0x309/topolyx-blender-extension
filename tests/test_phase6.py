"""Phase 6 테스트 — 개선된 공유 유틸리티 및 reader 검증.

Usage:
    blender -b -P tests/test_phase6.py
"""

import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트(익스텐션 디렉터리)를 패키지로 임포트할 수 있도록 상위 디렉터리를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy
from mathutils import Matrix, Quaternion, Vector

from topolyx_blender_extension.topolyx_attribute import topolyx_component_type_to_blender
from topolyx_blender_extension.topolyx_binary import BinaryBuffer, BinaryBufferReader
from topolyx_blender_extension.topolyx_coordinate import CoordinateConverter
from topolyx_blender_extension.topolyx_reader import read_topolyx
from topolyx_blender_extension.topolyx_types import CoordinateSystem
from topolyx_blender_extension.topolyx_utils import (
    column_major_list_to_matrix,
    matrix_to_column_major_list,
)
from topolyx_blender_extension.tests import common


def test_inverse_coordinate_conversion():
    """CoordinateConverter의 역변환이 정방향 변환을 되돌리는지 확인한다."""
    converter = CoordinateConverter("TOPOLYX_DEFAULT")

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


def test_topolyx_component_type_to_blender():
    """Topolyx attribute 타입을 Blender 타입으로 올바르게 환산하는지 확인한다."""
    assert topolyx_component_type_to_blender("F32", 1) == ("FLOAT", "value")
    assert topolyx_component_type_to_blender("F32", 2) == ("FLOAT2", "vector")
    assert topolyx_component_type_to_blender("F32", 3) == ("FLOAT_VECTOR", "vector")
    assert topolyx_component_type_to_blender("F32", 4) == ("FLOAT_COLOR", "color")
    assert topolyx_component_type_to_blender("U8", 4) == ("BYTE_COLOR", "color")
    assert topolyx_component_type_to_blender("I8", 1) == ("INT8", "value")
    assert topolyx_component_type_to_blender("I32", 1) == ("INT", "value")
    assert topolyx_component_type_to_blender("I32", 2) == ("INT32_2D", "value")
    assert topolyx_component_type_to_blender("U32", 1) == ("INT", "value")
    assert topolyx_component_type_to_blender("U32", 2) == ("INT32_2D", "value")

    try:
        topolyx_component_type_to_blender("U32", 3)
        raise AssertionError("Expected ValueError for unsupported U32x3")
    except ValueError:
        pass

    print("test_topolyx_component_type_to_blender passed")


def test_read_topolyx():
    """topolyx_reader가 익스포트한 파일을 올바르게 파싱하는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "reader_cube")
        topolyx_file, bin_data = read_topolyx(json_path)

        assert topolyx_file.header.format == "Topolyx"
        assert topolyx_file.header.version == "0.3"
        assert topolyx_file.buffer.byte_length == len(bin_data)
        assert len(topolyx_file.objects) == 1
        assert len(topolyx_file.meshes) == 1

        mesh = topolyx_file.meshes[0]
        assert mesh.element_counts.vertices == 8
        assert mesh.element_counts.edges == 12
        assert mesh.element_counts.faces == 6
        assert mesh.element_counts.corners == 24

        obj = topolyx_file.objects[0]
        assert obj.type == "MESH"
        assert obj.index == 0
        assert len(obj.transform) == 16
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_read_topolyx passed")


def test_from_coordinate_system():
    """CoordinateSystem 객체로부터 생성한 변환기가 preset 변환기와 동일한지 확인한다."""
    preset_converter = CoordinateConverter("TOPOLYX_DEFAULT")
    cs_converter = CoordinateConverter.from_coordinate_system(
        CoordinateSystem(
            up_axis="+Z",
            forward_axis="+Y",
            handedness="RIGHT",
            winding="CCW",
            meters_per_unit=1.0,
        )
    )

    pos = Vector((1.0, 2.0, 3.0))
    assert (
        preset_converter.convert_position(pos) - cs_converter.convert_position(pos)
    ).length < 1e-6
    assert (
        preset_converter.inverse_convert_position(pos)
        - cs_converter.inverse_convert_position(pos)
    ).length < 1e-6

    print("test_from_coordinate_system passed")


def test_arbitrary_coordinate_system():
    """임의의 right-handed 좌표계에서 양방향 변환이 정확한지 확인한다."""
    cs = CoordinateSystem(
        up_axis="+Y",
        forward_axis="+Z",
        handedness="RIGHT",
        winding="CCW",
        meters_per_unit=1.0,
    )
    converter = CoordinateConverter.from_coordinate_system(cs)

    pos = Vector((1.0, 2.0, 3.0))
    converted = converter.convert_position(pos)
    recovered = converter.inverse_convert_position(converted)
    assert (pos - recovered).length < 1e-6

    matrix = Matrix.Translation(Vector((4.0, 5.0, 6.0)))
    converted_matrix = converter.convert_matrix(matrix)
    recovered_matrix = converter.inverse_convert_matrix(converted_matrix)
    assert (matrix.to_translation() - recovered_matrix.to_translation()).length < 1e-6

    print("test_arbitrary_coordinate_system passed")


def test_winding_property():
    """converter.winding이 CoordinateSystem의 winding을 올바르게 반환하는지 확인한다."""
    converter_ccw = CoordinateConverter.from_coordinate_system(
        CoordinateSystem(winding="CCW")
    )
    converter_cw = CoordinateConverter.from_coordinate_system(
        CoordinateSystem(winding="CW")
    )

    assert converter_ccw.winding == "CCW"
    assert converter_cw.winding == "CW"

    print("test_winding_property passed")


def test_meters_per_unit_scaling():
    """meters_per_unit이 위치와 행렬 변환에 올바르게 적용되는지 확인한다."""
    cs = CoordinateSystem(
        up_axis="+Z",
        forward_axis="+Y",
        handedness="RIGHT",
        winding="CCW",
        meters_per_unit=2.0,
    )
    converter = CoordinateConverter.from_coordinate_system(cs)

    pos = Vector((1.0, 2.0, 3.0))
    blender_pos = converter.inverse_convert_position(pos)
    assert (blender_pos - Vector((2.0, 4.0, 6.0))).length < 1e-6

    source_pos = converter.convert_position(blender_pos)
    assert (source_pos - pos).length < 1e-6

    matrix = Matrix.Translation(Vector((3.0, 0.0, 0.0)))
    blender_matrix = converter.inverse_convert_matrix(matrix)
    expected_translation = Vector((6.0, 0.0, 0.0))
    assert (
        blender_matrix.to_translation() - expected_translation
    ).length < 1e-6

    print("test_meters_per_unit_scaling passed")


def test_invalid_coordinate_system_rejected():
    """Left-handed이거나 평행한 축을 가진 좌표계는 생성 시 거부되어야 한다."""
    try:
        CoordinateConverter.from_coordinate_system(
            CoordinateSystem(
                up_axis="+Z",
                forward_axis="+Z",
                handedness="RIGHT",
                winding="CCW",
            )
        )
        raise AssertionError("Expected ValueError for parallel axes")
    except ValueError:
        pass

    try:
        CoordinateConverter.from_coordinate_system(
            CoordinateSystem(
                up_axis="+Z",
                forward_axis="+Y",
                handedness="LEFT",
                winding="CCW",
            )
        )
        raise AssertionError("Expected ValueError for left-handed system")
    except ValueError:
        pass

    print("test_invalid_coordinate_system_rejected passed")


def test_custom_coordinate_system_export():
    """CUSTOM preset과 up_axis/forward_axis/meters_per_unit가 파일에 반영되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir,
            "custom_cs",
            coordinate_system_preset="CUSTOM",
            up_axis="+Y",
            forward_axis="+Z",
            handedness="RIGHT",
            winding="CW",
            meters_per_unit=2.0,
        )
        data, _ = common.load_result(json_path, bin_path)

        cs = data["coordinate_system"]
        assert cs["up_axis"] == "+Y"
        assert cs["forward_axis"] == "+Z"
        assert cs["handedness"] == "RIGHT"
        assert cs["winding"] == "CW"
        assert abs(cs["meters_per_unit"] - 2.0) < 1e-6
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_custom_coordinate_system_export passed")


def test_rotation_tangent_conversion_round_trip():
    """ROTATION/TANGENT semantic attribute의 좌표계 변환이 round-trip으로 복원된다."""
    converter = CoordinateConverter.from_coordinate_system(
        CoordinateSystem(
            up_axis="+Y",
            forward_axis="+Z",
            handedness="RIGHT",
            winding="CCW",
            meters_per_unit=1.0,
        )
    )

    q = Quaternion((0.5, 0.5, 0.5, 0.5))
    converted = converter.convert_rotation(q)
    recovered = converter.inverse_convert_rotation(converted)
    dot = abs(q.dot(recovered))
    assert abs(dot - 1.0) < 1e-6

    t = Vector((1.0, 0.0, 0.0, 1.0))
    converted_t = converter.convert_tangent(t)
    recovered_t = converter.inverse_convert_tangent(converted_t)
    assert (t - recovered_t).length < 1e-6

    print("test_rotation_tangent_conversion_round_trip passed")


def main():
    common.reset_addon()
    test_inverse_coordinate_conversion()
    test_matrix_serialization_round_trip()
    test_binary_buffer_reader()
    test_topolyx_component_type_to_blender()
    test_from_coordinate_system()
    test_arbitrary_coordinate_system()
    test_winding_property()
    test_meters_per_unit_scaling()
    test_invalid_coordinate_system_rejected()
    test_custom_coordinate_system_export()
    test_rotation_tangent_conversion_round_trip()
    test_read_topolyx()
    print("All Phase 6 tests passed")


if __name__ == "__main__":
    main()
