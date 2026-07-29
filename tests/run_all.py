"""Phase 0~9 tests를 하나의 Blender 백그라운드 프로세스에서 순차 실행한다.

Usage:
    blender -b -P tests/run_all.py

종료 코드:
    0 — 모든 테스트 통과
    1 — 하나 이상의 테스트 실패
"""

import sys
import traceback
from pathlib import Path

# run_all.py은 topolyx_blender_extension 패키지(프로젝트 루트)를 직접 임포트해야 하므로
# 프로젝트 루트의 상위 디렉터리를 sys.path에 추가한다.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root.parent))

from topolyx_blender_extension.tests import (
    test_phase0,
    test_phase1,
    test_phase2,
    test_phase3,
    test_phase4,
    test_phase5,
    test_phase6,
    test_phase7,
    test_phase8,
    test_phase9,
)


_TEST_MODULES = [
    test_phase0,
    test_phase1,
    test_phase2,
    test_phase3,
    test_phase4,
    test_phase5,
    test_phase6,
    test_phase7,
    test_phase8,
    test_phase9,
]


def main() -> int:
    failed = []

    for module in _TEST_MODULES:
        module_name = module.__name__.split(".")[-1]
        print(f"\n========== Running {module_name} ==========")
        try:
            module.main()
        except Exception as exc:
            print(f"FAILED: {module_name}")
            traceback.print_exc()
            failed.append((module_name, exc))

    print("\n========== Summary ==========")
    if not failed:
        print("All Phase 0~9 tests passed")
        return 0

    print(f"{len(failed)} test module(s) failed:")
    for module_name, exc in failed:
        print(f"  - {module_name}: {exc}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
