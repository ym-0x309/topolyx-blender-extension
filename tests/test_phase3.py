"""Phase 3 테스트 — attribute 익스포트 검증.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase3.py
"""

import struct
import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy

from blender_mattr_exporter.tests import common


def test_default_cube_with_uvmap():
    """Default Cube 기본 익스포트 시 UVMap attribute가 명세 예시와 일치하는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "cube")
        data, bin_data = common.load_result(json_path, bin_path)

        mesh = data["meshes"][0]
        assert mesh["element_counts"] == {
            "vertices": 8,
            "edges": 12,
            "faces": 6,
            "corners": 24,
        }

        attr = common.find_attribute(data, "UVMap")
        assert attr["domain"] == "CORNER"

        desc = attr["data"]
        assert desc["component_type"] == "F32"
        assert desc["component_count"] == 2
        assert desc["element_count"] == 24
        assert desc["byte_offset"] == 412
        assert desc["byte_length"] == 192

        assert data["buffer"]["byte_length"] == 604
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_default_cube_with_uvmap passed")


def test_export_attributes_disabled():
    """export_attributes=False일 때 attributes가 비어 있고 topology-only 길이를 유지한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "cube_no_attrs", export_attributes=False
        )
        data, bin_data = common.load_result(json_path, bin_path)

        mesh = data["meshes"][0]
        assert mesh["attributes"] == []
        assert data["buffer"]["byte_length"] == 412
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_export_attributes_disabled passed")


def test_custom_point_float_attribute():
    """POINT domain float attribute가 F32×1로 저장되는지 확인한다."""
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
        data, bin_data = common.load_result(json_path, bin_path)

        attr = common.find_attribute(data, "PointFloat")
        assert attr["domain"] == "POINT"
        desc = attr["data"]
        assert desc["component_type"] == "F32"
        assert desc["component_count"] == 1
        assert desc["element_count"] == 8

        common.assert_f32_values(bin_data, desc, values)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_custom_point_float_attribute passed")


def test_custom_face_int_attribute():
    """FACE domain int attribute가 I32×1로 저장되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = [i * 10 for i in range(len(mesh.polygons))]
    attr = mesh.attributes.new(name="FaceInt", type="INT", domain="FACE")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "face_int")
        data, bin_data = common.load_result(json_path, bin_path)

        attr = common.find_attribute(data, "FaceInt")
        assert attr["domain"] == "FACE"
        desc = attr["data"]
        assert desc["component_type"] == "I32"
        assert desc["component_count"] == 1
        assert desc["element_count"] == 6

        common.assert_i32_values(bin_data, desc, values)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_custom_face_int_attribute passed")


def test_vertex_color_float():
    """FLOAT_COLOR attribute가 F32×4로 저장되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = []
    for i in range(len(mesh.loops)):
        values.extend([0.1, 0.2, 0.3, 0.4])
    attr = mesh.attributes.new(name="FloatColor", type="FLOAT_COLOR", domain="CORNER")
    attr.data.foreach_set("color", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "float_color")
        data, bin_data = common.load_result(json_path, bin_path)

        attr = common.find_attribute(data, "FloatColor")
        assert attr["domain"] == "CORNER"
        desc = attr["data"]
        assert desc["component_type"] == "F32"
        assert desc["component_count"] == 4
        assert desc["element_count"] == 24

        common.assert_f32_values(bin_data, desc, values)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_vertex_color_float passed")


def test_vertex_color_byte():
    """BYTE_COLOR attribute가 0~1 범위의 F32×4로 저장되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = []
    for i in range(len(mesh.loops)):
        values.extend([1.0, 0.0, 0.25, 1.0])
    attr = mesh.attributes.new(name="ByteColor", type="BYTE_COLOR", domain="CORNER")
    attr.data.foreach_set("color", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "byte_color")
        data, bin_data = common.load_result(json_path, bin_path)

        attr = common.find_attribute(data, "ByteColor")
        assert attr["domain"] == "CORNER"
        desc = attr["data"]
        assert desc["component_type"] == "F32"
        assert desc["component_count"] == 4
        assert desc["element_count"] == 24

        count = desc["element_count"] * desc["component_count"]
        actual = struct.unpack_from(f"<{count}f", bin_data, desc["byte_offset"])
        for i in range(0, len(actual), 4):
            r, g, b, a = actual[i], actual[i + 1], actual[i + 2], actual[i + 3]
            assert abs(r - 1.0) < 1e-6
            assert abs(g - 0.0) < 1e-6
            assert abs(b - 0.25) < 0.01  # sRGB byte roundtrip 허용
            assert abs(a - 1.0) < 1e-6
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_vertex_color_byte passed")


def test_exclude_internal_attributes():
    """'.'로 시작하는 내장 attribute와 'position'이 출력에 포함되지 않는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "cube_filtered")
        data, bin_data = common.load_result(json_path, bin_path)

        names = {attr["name"] for attr in data["meshes"][0]["attributes"]}
        for name in names:
            assert not name.startswith("."), f"Internal attribute exported: {name}"
        assert "position" not in names
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_exclude_internal_attributes passed")


def test_exclude_by_name():
    """Excluded Attributes에 지정한 이름이 제외되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = [float(i) for i in range(len(mesh.vertices))]
    attr = mesh.attributes.new(name="SkipMe", type="FLOAT", domain="POINT")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir,
            "excluded",
            excluded_attribute_names="SkipMe",
        )
        data, bin_data = common.load_result(json_path, bin_path)

        names = {attr["name"] for attr in data["meshes"][0]["attributes"]}
        assert "SkipMe" not in names
        assert "UVMap" in names
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_exclude_by_name passed")


def test_unsupported_boolean_skipped():
    """BOOLEAN attribute가 오류 없이 제외되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "bool_skipped")
        data, bin_data = common.load_result(json_path, bin_path)

        names = {attr["name"] for attr in data["meshes"][0]["attributes"]}
        assert "sharp_face" not in names
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_unsupported_boolean_skipped passed")


def test_empty_mesh_attributes():
    """빈 메시의 attributes가 비어 있고 validator를 통과하는지 확인한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("EmptyMesh")
    obj = bpy.data.objects.new("EmptyObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "empty")
        data, bin_data = common.load_result(json_path, bin_path)

        assert data["meshes"][0]["attributes"] == []
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_empty_mesh_attributes passed")


def test_uv_map_values():
    """Default Cube UVMap의 첫 몇 개 값이 예상과 일치하는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "uv_values")
        data, bin_data = common.load_result(json_path, bin_path)

        attr = common.find_attribute(data, "UVMap")
        desc = attr["data"]
        values = struct.unpack_from(
            f"<{desc['element_count'] * desc['component_count']}f",
            bin_data,
            desc["byte_offset"],
        )
        # Default Cube의 첫 두 UV 좌표는 (0.375, 0.0), (0.625, 0.0) 등으로 시작한다.
        assert abs(values[0] - 0.375) < 1e-6
        assert abs(values[1] - 0.0) < 1e-6
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_uv_map_values passed")


def main():
    common.reset_addon()
    test_default_cube_with_uvmap()
    test_export_attributes_disabled()
    test_custom_point_float_attribute()
    test_custom_face_int_attribute()
    test_vertex_color_float()
    test_vertex_color_byte()
    test_exclude_internal_attributes()
    test_exclude_by_name()
    test_unsupported_boolean_skipped()
    test_empty_mesh_attributes()
    test_uv_map_values()
    print("All Phase 3 tests passed")


if __name__ == "__main__":
    main()
