"""Phase 5 테스트 — 엣지 케이스 및 검증 강화.

Usage:
    blender -b -P blender_topolyx_exporter/tests/test_phase5.py
"""

import json
import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy

from blender_topolyx_exporter import topolyx_validator
from blender_topolyx_exporter.tests import common


def test_ngon():
    """5각형 N-gon이 정상적으로 익스포트되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_circle_add(vertices=5, fill_type="NGON", radius=1)

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "ngon")
        data, bin_data = common.load_result(json_path, bin_path)

        mesh = data["meshes"][0]
        counts = mesh["element_counts"]
        assert counts["vertices"] == 5
        assert counts["faces"] == 1
        assert counts["corners"] == 5

        face_offsets = mesh["topology"]["face_offsets"]
        assert face_offsets["element_count"] == 2
        assert face_offsets["byte_length"] == 8
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_ngon passed")


def test_mixed_triangle_quad_ngon():
    """triangle, quad, pentagon이 혼합된 메시를 익스포트한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("MixedMesh")
    verts = [
        (0, 0, 0),
        (2, 0, 0),
        (2, 2, 0),
        (0, 2, 0),
        (1, 3, 0),
        (3, 3, 0),
    ]
    faces = [(0, 1, 2, 3), (2, 3, 4), (2, 4, 5)]  # quad, tri, tri
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new("MixedObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "mixed")
        data, bin_data = common.load_result(json_path, bin_path)

        mesh = data["meshes"][0]
        counts = mesh["element_counts"]
        assert counts["faces"] == 3
        # quad(4) + tri(3) + tri(3) = 10 corners
        assert counts["corners"] == 10

        face_offsets_desc = mesh["topology"]["face_offsets"]
        common.assert_u32_values(bin_data, face_offsets_desc, [0, 4, 7, 10])
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_mixed_triangle_quad_ngon passed")


def test_loose_vertex():
    """loose vertex를 포함한 메시가 정상적으로 익스포트된다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("LooseVertexMesh")
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    mesh.from_pydata(verts, [], [])
    mesh.update()

    obj = bpy.data.objects.new("LooseVertexObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "loose_vertex")
        data, bin_data = common.load_result(json_path, bin_path)

        mesh = data["meshes"][0]
        assert mesh["element_counts"]["vertices"] == 3
        assert mesh["element_counts"]["faces"] == 0
        assert mesh["element_counts"]["corners"] == 0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_loose_vertex passed")


def test_loose_edge():
    """loose edge를 포함한 메시가 정상적으로 익스포트된다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("LooseEdgeMesh")
    verts = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
    edges = [(0, 1), (2, 0)]
    mesh.from_pydata(verts, edges, [])
    mesh.update()

    obj = bpy.data.objects.new("LooseEdgeObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "loose_edge")
        data, bin_data = common.load_result(json_path, bin_path)

        mesh = data["meshes"][0]
        assert mesh["element_counts"]["vertices"] == 3
        assert mesh["element_counts"]["edges"] == 2
        assert mesh["element_counts"]["faces"] == 0
        assert mesh["element_counts"]["corners"] == 0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_loose_edge passed")


def test_edge_domain_attribute():
    """EDGE domain float attribute가 F32×1로 저장되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = [float(i) for i in range(len(mesh.edges))]
    attr = mesh.attributes.new(name="EdgeFloat", type="FLOAT", domain="EDGE")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "edge_attr")
        data, bin_data = common.load_result(json_path, bin_path)

        attr = common.find_attribute(data, "EdgeFloat")
        assert attr["domain"] == "EDGE"
        desc = attr["data"]
        assert desc["component_type"] == "F32"
        assert desc["component_count"] == 1
        assert desc["element_count"] == len(mesh.edges)

        common.assert_f32_values(bin_data, desc, values)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_edge_domain_attribute passed")


def test_multiple_attributes():
    """UVMap, FLOAT_COLOR, POINT float attribute가 동시에 저장된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    point_values = [float(i) for i in range(len(mesh.vertices))]
    point_attr = mesh.attributes.new(name="PointFloat", type="FLOAT", domain="POINT")
    point_attr.data.foreach_set("value", point_values)

    color_values = []
    for i in range(len(mesh.loops)):
        color_values.extend([0.1, 0.2, 0.3, 0.4])
    color_attr = mesh.attributes.new(name="FloatColor", type="FLOAT_COLOR", domain="CORNER")
    color_attr.data.foreach_set("color", color_values)

    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "multi_attr")
        data, bin_data = common.load_result(json_path, bin_path)

        attr_names = {attr["name"] for attr in data["meshes"][0]["attributes"]}
        assert "UVMap" in attr_names
        assert "PointFloat" in attr_names
        assert "FloatColor" in attr_names

        common.assert_f32_values(
            bin_data, common.find_attribute(data, "PointFloat")["data"], point_values
        )
        common.assert_f32_values(
            bin_data, common.find_attribute(data, "FloatColor")["data"], color_values
        )
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_multiple_attributes passed")


def test_negative_int_attribute():
    """음수 값을 포함한 INT attribute가 I32로 저장된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data

    values = [-i for i in range(len(mesh.vertices))]
    attr = mesh.attributes.new(name="NegInt", type="INT", domain="POINT")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "neg_int")
        data, bin_data = common.load_result(json_path, bin_path)

        attr = common.find_attribute(data, "NegInt")
        assert attr["domain"] == "POINT"
        desc = attr["data"]
        assert desc["component_type"] == "I32"
        common.assert_i32_values(bin_data, desc, values)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_negative_int_attribute passed")


def test_large_coordinates():
    """큰 좌표값을 가진 메시가 정밀도 손실 없이 저장된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1e6, 2e6, 3e6))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "large_coords", coordinate_system_preset="BLENDER"
        )
        data, bin_data = common.load_result(json_path, bin_path)

        transform = data["objects"][0]["transform"]
        assert abs(transform[12] - 1e6) < 1.0
        assert abs(transform[13] - 2e6) < 1.0
        assert abs(transform[14] - 3e6) < 1.0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_large_coordinates passed")


def test_empty_mesh_with_attributes_enabled():
    """빈 메시에서 export_attributes=True여도 정상 종료한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("EmptyMesh")
    obj = bpy.data.objects.new("EmptyObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "empty_attrs")
        data, bin_data = common.load_result(json_path, bin_path)

        assert data["meshes"][0]["attributes"] == []
        assert data["buffer"]["byte_length"] == 4
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_empty_mesh_with_attributes_enabled passed")


def test_no_mesh_objects_cancelled():
    """내보낼 메시가 없으면 Operator가 CANCELLED를 반환한다."""
    common.clear_scene()

    tmpdir = common.tempdir()
    try:
        json_path = tmpdir / "empty_scene.tlyx.json"
        # Blender에서 Operator가 ERROR를 report하면 bpy.ops.* 호출 시 RuntimeError가 발생한다.
        try:
            bpy.ops.export_mesh.tlyx(filepath=str(json_path))
            raise AssertionError("Operator should have failed with no mesh objects")
        except RuntimeError as exc:
            assert "No mesh objects to export" in str(exc), f"Unexpected error: {exc}"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_no_mesh_objects_cancelled passed")


def test_validator_catches_corrupted_json():
    """validator가 의도적으로 손상된 JSON을 거부하는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "valid_cube")
        # 검증 통과 확인
        common.load_result(json_path, bin_path)

        # JSON을 손상시킨다: vertices 수를 틀리게 변경
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["meshes"][0]["element_counts"]["vertices"] = 999
        corrupted_path = tmpdir / "corrupted.tlyx.json"
        with open(corrupted_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        try:
            topolyx_validator.validate_topolyx_file(corrupted_path, bin_path)
            raise AssertionError("Validator should have rejected corrupted JSON")
        except topolyx_validator.TopolyxValidationError:
            pass  # 예상된 동작
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_validator_catches_corrupted_json passed")


def main():
    common.reset_addon()
    test_ngon()
    test_mixed_triangle_quad_ngon()
    test_loose_vertex()
    test_loose_edge()
    test_edge_domain_attribute()
    test_multiple_attributes()
    test_negative_int_attribute()
    test_large_coordinates()
    test_empty_mesh_with_attributes_enabled()
    test_no_mesh_objects_cancelled()
    test_validator_catches_corrupted_json()
    print("All Phase 5 tests passed")


if __name__ == "__main__":
    main()
