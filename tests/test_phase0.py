"""Phase 0 smoke test — runs inside Blender.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase0.py

This script registers the addon classes from the source directory,
invokes the export operator with a temp path, and verifies that the operator
returns {'FINISHED'}.

If the same addon is already installed/enabled in Blender's user preferences,
it is temporarily disabled to avoid class registration conflicts.
"""

import sys
import tempfile
from pathlib import Path

import bpy

ADDON_MODULE = "blender_mattr_exporter"


def main():
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    # 이미 활성화된 동일 ID의 애드온이 있다면 비활성화
    if ADDON_MODULE in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)

    # 기존에 로드된 모듈 캐시를 제거하여 소스 디렉터리에서 재임포트
    for name in list(sys.modules.keys()):
        if name == ADDON_MODULE or name.startswith(ADDON_MODULE + "."):
            del sys.modules[name]

    import blender_mattr_exporter

    blender_mattr_exporter.register()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "test.mattr.json"
        result = bpy.ops.export_mesh.mattr(filepath=str(test_path))
        assert result == {"FINISHED"}, f"Operator returned {result}"
        print(f"Phase 0 smoke test passed: {test_path}")


if __name__ == "__main__":
    main()
