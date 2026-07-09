# MATTR Exporter Testing

본 문서는 MATTR Exporter의 테스트 실행 방법을 설명한다.

## 테스트 구조

```text
blender_mattr_exporter/tests/
├── common.py           # 공통 테스트 헬퍼
├── run_all.py          # Phase 0~8 통합 테스트 러너
├── test_phase0.py      # Extension 등록/Operator smoke test
├── test_phase1.py      # 토폴로지 익스포트 검증
├── test_phase2.py      # 좌표계 변환 및 Object Transform 검증
├── test_phase3.py      # attribute 익스포트 검증
├── test_phase4.py      # 다중 오브젝트 및 메시 공유 검증
├── test_phase5.py      # 엣지 케이스 및 검증 강화
├── test_phase6.py      # 공유 유틸리티 및 reader 검증
├── test_phase7.py      # topology import 검증
└── test_phase8.py      # attribute import 검증
```

## 사전 요구 사항

- Blender 5.1 이상이 설치되어 있어야 한다.
- `blender` 명령이 PATH에 있거나, 전체 경로를 사용해야 한다.

## 단일 테스트 실행

각 테스트는 Blender 백그라운드 모드에서 실행한다.

```bash
blender -b -P blender_mattr_exporter/tests/test_phase0.py
blender -b -P blender_mattr_exporter/tests/test_phase1.py
blender -b -P blender_mattr_exporter/tests/test_phase2.py
blender -b -P blender_mattr_exporter/tests/test_phase3.py
blender -b -P blender_mattr_exporter/tests/test_phase4.py
blender -b -P blender_mattr_exporter/tests/test_phase5.py
blender -b -P blender_mattr_exporter/tests/test_phase6.py
blender -b -P blender_mattr_exporter/tests/test_phase7.py
blender -b -P blender_mattr_exporter/tests/test_phase8.py
```

## 통합 테스트 실행

`run_all.py`는 하나의 Blender 프로세스에서 Phase 0~8을 순차적으로 실행한다.

```bash
blender -b -P blender_mattr_exporter/tests/run_all.py
```

종료 코드:

- `0`: 모든 테스트 통과
- `1`: 하나 이상의 테스트 실패

## CI 연동 예시

GitHub Actions 등에서 사용할 수 있는 간단한 예시이다. Blender를 CI 환경에 설치하는 방법은 프로젝트 외부 의존성이 크므로, 여기서는 Blender가 이미 설치되어 있다고 가정한다.

```yaml
name: MATTR Exporter Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run MATTR Exporter tests
        run: blender -b -P blender_mattr_exporter/tests/run_all.py
```

## 테스트 작성 가이드

새로운 테스트를 추가할 때는 `tests/common.py`의 헬퍼 함수를 사용하는 것을 권장한다.

```python
from blender_mattr_exporter.tests import common

def test_my_feature():
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "my_feature")
        data, bin_data = common.load_result(json_path, bin_path)
        # 추가 검증
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
```

## 주의 사항

- 동일한 애드온 ID(`blender_mattr_exporter`)가 `~/.config/blender/5.1/extensions/user_default/`에 이미 설치되어 있으면, 테스트가 등록 충돌로 실패할 수 있다. 이 경우 Blender 환경 설정에서 해당 애드온을 비활성화하거나 제거한다.
