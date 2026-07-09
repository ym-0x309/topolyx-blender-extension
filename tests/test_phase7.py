"""Phase 7 tests — MATTR import Operator smoke tests.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase7.py
"""

import sys
from pathlib import Path

# Run standalone: add project root to sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy
from mathutils import Matrix

from blender_mattr_exporter.tests import common


def test_import_operator_basic():
    """Default Cube를 export 후 import Operator로 복원한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "cube")
        common.clear_scene()

        common.import_mattr_file(json_path)

        assert len(bpy.context.scene.objects) == 1
        obj = bpy.context.active_object
        assert obj is not None
        assert obj.type == "MESH"
        mesh = obj.data
        assert len(mesh.vertices) == 8
        assert len(mesh.edges) == 12
        assert len(mesh.polygons) == 6
        assert len(mesh.loops) == 24
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_operator_basic passed")


def test_import_without_attributes():
    """import_attributes=False일 때 attribute가 복원되지 않는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "cube")
        common.clear_scene()

        common.import_mattr_file(json_path, import_attributes=False)

        obj = bpy.context.active_object
        assert obj.type == "MESH"
        # Default Cube에는 UVMap이 있지만, import_attributes=False이면 복원되지 않아야 한다.
        attr_names = {attr.name for attr in obj.data.attributes}
        assert "UVMap" not in attr_names
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_without_attributes passed")


def test_import_with_apply_transform():
    """apply_transform=True일 때 mesh에 transform이 굽고 object matrix가 identity가 된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "cube", coordinate_system_preset="BLENDER"
        )
        common.clear_scene()

        common.import_mattr_file(json_path, apply_transform=True)

        obj = bpy.context.active_object
        assert obj.type == "MESH"

        # Object transform은 identity로 reset된다.
        for i in range(4):
            for j in range(4):
                expected = 1.0 if i == j else 0.0
                assert abs(obj.matrix_world[i][j] - expected) < 1e-6

        # Mesh vertex는 world 좌표에 있어야 한다.
        xs = [v.co.x for v in obj.data.vertices]
        ys = [v.co.y for v in obj.data.vertices]
        zs = [v.co.z for v in obj.data.vertices]
        # size=2 cube가 (1,2,3) translation만 적용된 경우
        assert min(xs) >= 0.0
        assert min(ys) >= 1.0
        assert min(zs) >= 2.0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_with_apply_transform passed")


def test_import_missing_file():
    """존재하지 않는 파일을 import하면 Operator가 실패한다."""
    common.clear_scene()
    tmpdir = common.tempdir()
    try:
        missing_path = tmpdir / "missing.mattr.json"
        try:
            common.import_mattr_file(missing_path)
            raise AssertionError("Import operator should have failed for missing file")
        except RuntimeError as exc:
            assert "MATTR import failed" in str(exc)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_missing_file passed")


def main():
    common.reset_addon()
    test_import_operator_basic()
    test_import_without_attributes()
    test_import_with_apply_transform()
    test_import_missing_file()
    print("All Phase 7 tests passed")


if __name__ == "__main__":
    main()
