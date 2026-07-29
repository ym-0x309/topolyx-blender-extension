"""Phase 1 테스트 — 토폴로지 익스포트 검증.

Usage:
    blender -b -P blender_topolyx_exporter/tests/test_phase1.py
"""

import struct
import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy

from blender_topolyx_exporter.tests import common


def test_default_cube():
    """Default Cube의 토폴로지가 명세 예시와 일치하는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "cube", export_attributes=False
        )
        data, bin_data = common.load_result(json_path, bin_path)

        mesh = data["meshes"][0]
        counts = mesh["element_counts"]
        assert counts == {"vertices": 8, "edges": 12, "faces": 6, "corners": 24}

        topo = mesh["topology"]
        assert topo["positions"]["byte_offset"] == 0
        assert topo["positions"]["byte_length"] == 96
        assert topo["edges"]["byte_offset"] == 96
        assert topo["edges"]["byte_length"] == 96
        assert topo["corner_vertices"]["byte_offset"] == 192
        assert topo["corner_vertices"]["byte_length"] == 96
        assert topo["corner_edges"]["byte_offset"] == 288
        assert topo["corner_edges"]["byte_length"] == 96
        assert topo["face_offsets"]["byte_offset"] == 384
        assert topo["face_offsets"]["byte_length"] == 28

        assert data["buffer"]["byte_length"] == 412
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_default_cube passed")


def test_transformed_cube():
    """변형이 적용된 오브젝트의 transform이 column-major로 직렬화되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))
    obj = bpy.context.active_object
    obj.rotation_euler = (0.1, 0.2, 0.3)

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir,
            "transformed_cube",
            coordinate_system_preset="BLENDER",
            export_attributes=False,
        )
        data, bin_data = common.load_result(json_path, bin_path)

        transform = data["objects"][0]["transform"]
        assert len(transform) == 16
        # column-major 직렬화에서 translation은 4번째 column(인덱스 12,13,14)에 위치
        assert abs(transform[12] - 1.0) < 1e-6
        assert abs(transform[13] - 2.0) < 1e-6
        assert abs(transform[14] - 3.0) < 1e-6

        # positions는 mesh local 좌표이므로 원점 중심 큐브 그대로여야 함
        positions_desc = data["meshes"][0]["topology"]["positions"]
        positions = struct.unpack_from(
            f"<{positions_desc['element_count'] * 3}f",
            bin_data,
            positions_desc["byte_offset"],
        )
        xs = positions[0::3]
        ys = positions[1::3]
        zs = positions[2::3]
        assert min(xs) == -1.0 and max(xs) == 1.0
        assert min(ys) == -1.0 and max(ys) == 1.0
        assert min(zs) == -1.0 and max(zs) == 1.0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_transformed_cube passed")


def test_empty_mesh():
    """빈 메시가 명세 조건을 만족하는지 확인한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("EmptyMesh")
    obj = bpy.data.objects.new("EmptyObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "empty", export_attributes=False
        )
        data, bin_data = common.load_result(json_path, bin_path)

        mesh = data["meshes"][0]
        counts = mesh["element_counts"]
        assert counts == {"vertices": 0, "edges": 0, "faces": 0, "corners": 0}
        assert mesh["topology"]["face_offsets"]["element_count"] == 1
        assert data["buffer"]["byte_length"] == 4
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_empty_mesh passed")


def test_ensure_topolyx_json_ext():
    """execute에서 사용하는 확장자 보정 로직을 검증한다."""
    from blender_topolyx_exporter.topolyx_export_operator import _ensure_topolyx_json_ext

    assert _ensure_topolyx_json_ext("model") == "model.tlyx.json"
    assert _ensure_topolyx_json_ext("model.json") == "model.tlyx.json"
    assert _ensure_topolyx_json_ext("model.tlyx") == "model.tlyx.json"
    assert _ensure_topolyx_json_ext("model.tlyx.json") == "model.tlyx.json"
    assert _ensure_topolyx_json_ext("/tmp/model") == "/tmp/model.tlyx.json"
    print("test_ensure_topolyx_json_ext passed")


def main():
    common.reset_addon()
    test_default_cube()
    test_transformed_cube()
    test_empty_mesh()
    test_ensure_topolyx_json_ext()
    print("All Phase 1 tests passed")


if __name__ == "__main__":
    main()
