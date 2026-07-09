"""Phase 8 테스트 — MATTR attribute의 Blender Mesh 복원 검증.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase8.py
"""

import array
import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy

from blender_mattr_exporter.mattr_attribute import mattr_component_type_to_blender
from blender_mattr_exporter.mattr_attribute_import import (
    _read_u32_as_i32,
    apply_attributes,
)
from blender_mattr_exporter.mattr_binary import BinaryBuffer, BinaryBufferReader
from blender_mattr_exporter.mattr_reader import read_mattr
from blender_mattr_exporter.tests import common


_TYPE_COMPONENT_COUNT = {
    "FLOAT": 1,
    "INT": 1,
    "FLOAT2": 2,
    "FLOAT_VECTOR": 3,
    "FLOAT_COLOR": 4,
    "BYTE_COLOR": 4,
    "INT32_2D": 2,
}


def _read_blender_attribute_values(blender_attr):
    """Blender attribute 값을 foreach_get으로 읽어 반환한다."""
    data_type = blender_attr.data_type
    component_count = _TYPE_COMPONENT_COUNT[data_type]
    element_count = len(blender_attr.data)
    total_count = element_count * component_count

    if data_type in ("FLOAT", "INT"):
        buf = array.array("f" if data_type == "FLOAT" else "i", [0]) * total_count
        prop = "value"
    elif data_type in ("FLOAT2", "FLOAT_VECTOR"):
        buf = array.array("f", [0.0]) * total_count
        prop = "vector"
    elif data_type in ("FLOAT_COLOR", "BYTE_COLOR"):
        buf = array.array("f", [0.0]) * total_count
        prop = "color"
    elif data_type == "INT32_2D":
        buf = array.array("i", [0]) * total_count
        prop = "value"
    else:
        raise ValueError(f"Unsupported data type for read-back: {data_type}")

    blender_attr.data.foreach_get(prop, buf)
    return list(buf)


def test_point_float_attribute():
    """POINT domain FLOAT attribute가 round-trip으로 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = [float(i) for i in range(len(mesh.vertices))]
    attr = mesh.attributes.new(name="PointFloat", type="FLOAT", domain="POINT")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "point_float")
        imported_mesh = common.import_topology_only(json_path, bin_path)
        mattr_file, bin_data = read_mattr(json_path)
        warnings = apply_attributes(
            imported_mesh, mattr_file.meshes[0].attributes, bin_data
        )
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_attr = imported_mesh.attributes.get("PointFloat")
        assert imported_attr is not None, "PointFloat attribute not found"
        assert imported_attr.data_type == "FLOAT"
        assert imported_attr.domain == "POINT"

        actual = _read_blender_attribute_values(imported_attr)
        assert actual == values
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_point_float_attribute passed")


def test_edge_int_attribute():
    """EDGE domain INT attribute가 round-trip으로 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = [i * 10 for i in range(len(mesh.edges))]
    attr = mesh.attributes.new(name="EdgeInt", type="INT", domain="EDGE")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "edge_int")
        imported_mesh = common.import_topology_only(json_path, bin_path)
        mattr_file, bin_data = read_mattr(json_path)
        warnings = apply_attributes(
            imported_mesh, mattr_file.meshes[0].attributes, bin_data
        )
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_attr = imported_mesh.attributes.get("EdgeInt")
        assert imported_attr is not None
        assert imported_attr.data_type == "INT"
        assert imported_attr.domain == "EDGE"

        actual = _read_blender_attribute_values(imported_attr)
        assert actual == values
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_edge_int_attribute passed")


def test_face_float_attribute():
    """FACE domain FLOAT attribute가 round-trip으로 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = [float(i) / 10.0 for i in range(len(mesh.polygons))]
    attr = mesh.attributes.new(name="FaceFloat", type="FLOAT", domain="FACE")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "face_float")
        imported_mesh = common.import_topology_only(json_path, bin_path)
        mattr_file, bin_data = read_mattr(json_path)
        warnings = apply_attributes(
            imported_mesh, mattr_file.meshes[0].attributes, bin_data
        )
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_attr = imported_mesh.attributes.get("FaceFloat")
        assert imported_attr is not None
        assert imported_attr.data_type == "FLOAT"
        assert imported_attr.domain == "FACE"

        actual = _read_blender_attribute_values(imported_attr)
        for a, e in zip(actual, values):
            assert abs(a - e) < 1e-6
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_face_float_attribute passed")


def test_corner_float_color_attribute():
    """CORNER domain FLOAT_COLOR attribute가 round-trip으로 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = []
    for i in range(len(mesh.loops)):
        values.extend([0.1, 0.2, 0.3, 0.4])
    attr = mesh.attributes.new(name="CornerColor", type="FLOAT_COLOR", domain="CORNER")
    attr.data.foreach_set("color", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "corner_color")
        imported_mesh = common.import_topology_only(json_path, bin_path)
        mattr_file, bin_data = read_mattr(json_path)
        warnings = apply_attributes(
            imported_mesh, mattr_file.meshes[0].attributes, bin_data
        )
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_attr = imported_mesh.attributes.get("CornerColor")
        assert imported_attr is not None
        assert imported_attr.data_type == "FLOAT_COLOR"
        assert imported_attr.domain == "CORNER"

        actual = _read_blender_attribute_values(imported_attr)
        for a, e in zip(actual, values):
            assert abs(a - e) < 1e-6
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_corner_float_color_attribute passed")


def test_uvmap_attribute():
    """Default Cube의 UVMap(FLOAT2/CORNER) attribute가 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    original_mesh = bpy.context.active_object.data
    original_values = _read_blender_attribute_values(
        original_mesh.attributes["UVMap"]
    )

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "uvmap_cube")
        imported_mesh = common.import_topology_only(json_path, bin_path)
        mattr_file, bin_data = read_mattr(json_path)
        warnings = apply_attributes(
            imported_mesh, mattr_file.meshes[0].attributes, bin_data
        )
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_attr = imported_mesh.attributes.get("UVMap")
        assert imported_attr is not None
        assert imported_attr.data_type == "FLOAT2"
        assert imported_attr.domain == "CORNER"

        actual = _read_blender_attribute_values(imported_attr)
        for a, e in zip(actual, original_values):
            assert abs(a - e) < 1e-6
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_uvmap_attribute passed")


def test_int32_2d_attribute():
    """POINT domain INT32_2D attribute가 round-trip으로 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = []
    for i in range(len(mesh.vertices)):
        values.extend([i, i * 10])
    attr = mesh.attributes.new(name="Int32_2D", type="INT32_2D", domain="POINT")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "int32_2d")
        imported_mesh = common.import_topology_only(json_path, bin_path)
        mattr_file, bin_data = read_mattr(json_path)
        warnings = apply_attributes(
            imported_mesh, mattr_file.meshes[0].attributes, bin_data
        )
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_attr = imported_mesh.attributes.get("Int32_2D")
        assert imported_attr is not None
        assert imported_attr.data_type == "INT32_2D"
        assert imported_attr.domain == "POINT"

        actual = _read_blender_attribute_values(imported_attr)
        assert actual == values
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_int32_2d_attribute passed")


def test_multiple_attributes():
    """여러 attribute가 동시에 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    point_values = [float(i) for i in range(len(mesh.vertices))]
    point_attr = mesh.attributes.new(name="PointFloat", type="FLOAT", domain="POINT")
    point_attr.data.foreach_set("value", point_values)

    color_values = []
    for _ in range(len(mesh.loops)):
        color_values.extend([0.1, 0.2, 0.3, 0.4])
    color_attr = mesh.attributes.new(name="CornerColor", type="FLOAT_COLOR", domain="CORNER")
    color_attr.data.foreach_set("color", color_values)

    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "multi_attr")
        imported_mesh = common.import_topology_only(json_path, bin_path)
        mattr_file, bin_data = read_mattr(json_path)
        warnings = apply_attributes(
            imported_mesh, mattr_file.meshes[0].attributes, bin_data
        )
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_point = imported_mesh.attributes.get("PointFloat")
        imported_color = imported_mesh.attributes.get("CornerColor")
        assert imported_point is not None
        assert imported_color is not None

        actual_point = _read_blender_attribute_values(imported_point)
        assert actual_point == point_values

        actual_color = _read_blender_attribute_values(imported_color)
        for a, e in zip(actual_color, color_values):
            assert abs(a - e) < 1e-6
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_multiple_attributes passed")


def test_reserved_attribute_name_renamed():
    """예약어 attribute 이름이 import 시 rename되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = [float(i) for i in range(len(mesh.vertices))]
    attr = mesh.attributes.new(name="ReservedPoint", type="FLOAT", domain="POINT")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "reserved_name")
        imported_mesh = common.import_topology_only(json_path, bin_path)
        mattr_file, bin_data = read_mattr(json_path)

        # 파일 내 attribute 이름을 예약어 "position"으로 강제 변경하여 collision 테스트
        reserved_attr = next(
            attr for attr in mattr_file.meshes[0].attributes if attr.name == "ReservedPoint"
        )
        reserved_attr.name = "position"
        warnings = apply_attributes(
            imported_mesh, mattr_file.meshes[0].attributes, bin_data
        )
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_attr = imported_mesh.attributes.get("import_position")
        assert imported_attr is not None

        actual = _read_blender_attribute_values(imported_attr)
        assert actual == values
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_reserved_attribute_name_renamed passed")


def test_u32_bit_cast_to_i32():
    """U32 attribute 값이 비트 패턴을 그대로 I32로 해석되는지 확인한다."""
    buffer = BinaryBuffer()
    u32_values = [0, 1, 0xFFFFFFFF, 0x80000000]
    offset = buffer.append_u32(u32_values)

    reader = BinaryBufferReader(buffer.to_bytes())
    i32_values = list(_read_u32_as_i32(reader, offset, len(u32_values)))

    assert i32_values == [0, 1, -1, -2147483648]

    # mattr_component_type_to_blender도 U32x1, U32x2를 INT/INT32_2D로 매핑하는지 확인
    assert mattr_component_type_to_blender("U32", 1) == ("INT", "value")
    assert mattr_component_type_to_blender("U32", 2) == ("INT32_2D", "value")

    print("test_u32_bit_cast_to_i32 passed")


def test_u32_unsupported_component_count():
    """U32x3 같은 지원하지 않는 component_count는 ValueError를 발생시켜야 한다."""
    try:
        mattr_component_type_to_blender("U32", 3)
        raise AssertionError("Expected ValueError for U32x3")
    except ValueError:
        pass

    print("test_u32_unsupported_component_count passed")


def main():
    common.reset_addon()
    test_point_float_attribute()
    test_edge_int_attribute()
    test_face_float_attribute()
    test_corner_float_color_attribute()
    test_uvmap_attribute()
    test_int32_2d_attribute()
    test_multiple_attributes()
    test_reserved_attribute_name_renamed()
    test_u32_bit_cast_to_i32()
    test_u32_unsupported_component_count()
    print("All Phase 8 tests passed")


if __name__ == "__main__":
    main()
