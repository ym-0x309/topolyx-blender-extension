"""Phase 1 테스트 — 토폴로지 익스포트 검증.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase1.py
"""

import json
import struct
import sys
import tempfile
from pathlib import Path

import bpy

ADDON_MODULE = "blender_mattr_exporter"


def _reset_addon():
    """소스 디렉터리의 애드온을 최신 상태로 등록한다."""
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    if ADDON_MODULE in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)

    for name in list(sys.modules.keys()):
        if name == ADDON_MODULE or name.startswith(ADDON_MODULE + "."):
            del sys.modules[name]

    import blender_mattr_exporter

    blender_mattr_exporter.register()
    return blender_mattr_exporter


def _clear_scene():
    """현재 씬의 모든 오브젝트를 삭제한다."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _export_active_object(
    tmpdir: Path, name: str, **operator_kwargs
) -> tuple[Path, Path]:
    """현재 active object를 익스포트하고 JSON/bin 경로를 반환한다."""
    json_path = tmpdir / f"{name}.mattr.json"
    result = bpy.ops.export_mesh.mattr(filepath=str(json_path), **operator_kwargs)
    assert result == {"FINISHED"}, f"Operator returned {result}"
    bin_path = json_path.with_name(json_path.stem + ".bin")
    return json_path, bin_path


def test_default_cube():
    """Default Cube의 토폴로지가 명세 예시와 일치하는지 확인한다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_active_object(tmpdir, "cube")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bin_data = bin_path.read_bytes()

        from blender_mattr_exporter import mattr_validator

        mattr_validator.validate_mattr(data, bin_data)

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

    print("test_default_cube passed")


def test_transformed_cube():
    """변형이 적용된 오브젝트의 transform이 column-major로 직렬화되는지 확인한다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))
    obj = bpy.context.active_object
    obj.rotation_euler = (0.1, 0.2, 0.3)

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_active_object(
            tmpdir, "transformed_cube", coordinate_system_preset="BLENDER"
        )

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bin_data = bin_path.read_bytes()

        from blender_mattr_exporter import mattr_validator

        mattr_validator.validate_mattr(data, bin_data)

        transform = data["objects"][0]["transform"]
        assert len(transform) == 16
        # column-major 직렬화에서 translation은 4번째 column(인덱스 12,13,14)에 위치
        assert abs(transform[12] - 1.0) < 1e-6
        assert abs(transform[13] - 2.0) < 1e-6
        assert abs(transform[14] - 3.0) < 1e-6

        # positions는 mesh local 좌표이므로 원점 중심 큐브 그대로여야 함
        positions_desc = data["meshes"][0]["topology"]["positions"]
        positions = struct.unpack_from(f"<{positions_desc['element_count'] * 3}f", bin_data, positions_desc["byte_offset"])
        xs = positions[0::3]
        ys = positions[1::3]
        zs = positions[2::3]
        assert min(xs) == -1.0 and max(xs) == 1.0
        assert min(ys) == -1.0 and max(ys) == 1.0
        assert min(zs) == -1.0 and max(zs) == 1.0

    print("test_transformed_cube passed")


def test_empty_mesh():
    """빈 메시가 명세 조건을 만족하는지 확인한다."""
    _clear_scene()
    mesh = bpy.data.meshes.new("EmptyMesh")
    obj = bpy.data.objects.new("EmptyObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_active_object(tmpdir, "empty")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bin_data = bin_path.read_bytes()

        from blender_mattr_exporter import mattr_validator

        mattr_validator.validate_mattr(data, bin_data)

        mesh = data["meshes"][0]
        counts = mesh["element_counts"]
        assert counts == {"vertices": 0, "edges": 0, "faces": 0, "corners": 0}
        assert mesh["topology"]["face_offsets"]["element_count"] == 1
        assert data["buffer"]["byte_length"] == 4

    print("test_empty_mesh passed")


def test_ensure_mattr_json_ext():
    """execute에서 사용하는 확장자 보정 로직을 검증한다."""
    from blender_mattr_exporter.mattr_export_operator import _ensure_mattr_json_ext

    assert _ensure_mattr_json_ext("model") == "model.mattr.json"
    assert _ensure_mattr_json_ext("model.json") == "model.mattr.json"
    assert _ensure_mattr_json_ext("model.mattr") == "model.mattr.json"
    assert _ensure_mattr_json_ext("model.mattr.json") == "model.mattr.json"
    assert _ensure_mattr_json_ext("/tmp/model") == "/tmp/model.mattr.json"
    print("test_ensure_mattr_json_ext passed")


def main():
    _reset_addon()
    test_default_cube()
    test_transformed_cube()
    test_empty_mesh()
    test_ensure_mattr_json_ext()
    print("All Phase 1 tests passed")


if __name__ == "__main__":
    main()
