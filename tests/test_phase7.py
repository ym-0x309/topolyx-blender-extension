"""Phase 7 tests — Topolyx import Operator smoke tests.

Usage:
    blender -b -P tests/test_phase7.py
"""

import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트(익스텐션 디렉터리)를 패키지로 임포트할 수 있도록 상위 디렉터리를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy

from topolyx_blender_extension.tests import common


def test_import_operator_basic():
    """Default Cube를 export 후 import Operator로 복원한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "cube")
        common.clear_scene()

        common.import_topolyx_file(json_path)

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

        common.import_topolyx_file(json_path, import_attributes=False)

        obj = bpy.context.active_object
        assert obj.type == "MESH"
        # Default Cube에는 UVMap이 있지만, import_attributes=False이면 복원되지 않아야 한다.
        attr_names = {attr.name for attr in obj.data.attributes}
        assert "UVMap" not in attr_names
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_without_attributes passed")


def test_import_missing_file():
    """존재하지 않는 파일을 import하면 Operator가 실패한다."""
    common.clear_scene()
    tmpdir = common.tempdir()
    try:
        missing_path = tmpdir / "missing.tlyx.json"
        try:
            common.import_topolyx_file(missing_path)
            raise AssertionError("Import operator should have failed for missing file")
        except RuntimeError as exc:
            assert "Topolyx import failed" in str(exc)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_missing_file passed")


def main():
    common.reset_addon()
    test_import_operator_basic()
    test_import_without_attributes()
    test_import_missing_file()
    print("All Phase 7 tests passed")


if __name__ == "__main__":
    main()
