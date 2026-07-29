"""Phase 0 smoke test — runs inside Blender.

Usage:
    blender -b -P blender_topolyx_exporter/tests/test_phase0.py

This script registers the addon classes from the source directory,
invokes the export operator with a temp path, and verifies that the operator
returns {'FINISHED'}.

If the same addon is already installed/enabled in Blender's user preferences,
it is temporarily disabled to avoid class registration conflicts.
"""

import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy

from blender_topolyx_exporter.tests import common


def main():
    common.reset_addon()
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        test_path = tmpdir / "test.tlyx.json"
        result = bpy.ops.export_mesh.tlyx(filepath=str(test_path))
        assert result == {"FINISHED"}, f"Operator returned {result}"
        print(f"Phase 0 smoke test passed: {test_path}")
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
