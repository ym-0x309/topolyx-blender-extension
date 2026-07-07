# MATTR Exporter Overview

## 목적

`MATTR Exporter`는 Blender의 메시 데이터를 `MATTR(Mesh Attribute & Topology Transfer Representation)` 포맷으로 낸 장하기 위한 Blender Extension(애드온)이다.

본 Extension은 Blender 5.1 이상을 대상으로 하며, 메시의 토폴로지(positions, edges, faces, corners)와 POINT/EDGE/FACE/CORNER 도메인의 attribute를 손실 없이 `.mattr.json` + `.mattr.bin` 파일 쌍으로 저장하는 것을 목표로 한다.

## 파일 구조

```text
blender_mattr_exporter/
├── blender_manifest.toml       # Extension 메타데이터 및 Blender 호환 정보
├── __init__.py                 # 애드온 등록/해제 및 메뉴 연결
├── mattr_export_operator.py    # 파일 저장 대화상자 및 익스포트 실행 Operator
├── mattr_properties.py         # 익스포트 옵션 PropertyGroup
├── mattr_writer.py             # JSON + binary 조립 진입점
├── mattr_types.py              # MATTR 포맷 데이터 모델
├── mattr_mesh.py               # Blender Mesh → MATTR 토폴로지 추출
├── mattr_attribute.py          # Blender Mesh Attribute → MATTR attribute 추출
├── mattr_binary.py             # 4바이트 정렬 binary 버퍼 빌더
├── mattr_validator.py          # 출력 파일 유효성 검증
    └── tests/
        ├── test_phase0.py          # Blender 낸 장기능 smoke test
        ├── test_phase1.py          # 토폴로지 익스포트 검증
        ├── test_phase2.py          # 좌표계 변환 검증
        ├── test_phase3.py          # attribute 익스포트 검증
        └── test_phase4.py          # 다중 오브젝트 및 메시 공유 검증
```

## Extension 생명주기

### 1. 설치 및 활성화

- 사용자가 `blender_manifest.toml`을 포함한 디렉터리를 Blender에 설치한다.
- Blender는 활성화 시 `__init__.py`의 `register()` 함수를 호출한다.

### 2. 등록

`register()`는 다음 항목들을 Blender에 등록한다.

- `MATTR_OT_export_mesh` Operator
- `MATTR_PG_export_settings` PropertyGroup
- `File > Export` 메뉴 항목

### 3. 사용 흐름

1. 사용자가 `File > Export > MATTR (.mattr.json)`를 선택한다.
2. `ExportHelper`를 상속한 Operator가 파일 저장 대화상자를 연다.
3. 사용자가 경로를 선택하고 Export를 누륩다.
4. Operator의 `execute()`가 호출되고, 대상 메시 오브젝트 목록을 `mattr_writer`에 전달한다.
5. `mattr_writer`는 각 오브젝트의 `obj.data`를 기반으로 `.mattr.json`과 `.mattr.bin`을 생성한다. 동일한 메시 데이터 블록은 한 번만 기록한다.

### 4. 비활성화

- Blender는 비활성화 시 `unregister()`를 호출한다.
- 등록된 Operator, PropertyGroup, 메뉴 항목을 모두 제거한다.

## 주요 설계 결정

- **원본 메시 사용**: 평가된 메시(evaluated mesh)가 아닌 `obj.data` 원본 데이터 블록을 낸 장한다.
- **좌표계 변환 지원**: 기본적으로 명세 예시 좌표계(`+Z` Up, `+Y` Forward, Right-handed, CCW)로 낸 장한다. Blender의 좌표계(`+Z` Up, `+Y` Forward)와 동일하므로, 현재 `MATTR_DEFAULT`와 `BLENDER` preset은 동일한 출력을 생성한다.
- **Object Transform 변환**: `object.transform`은 mesh local space 좌표를 file world space 좌표로 변환하는 행렬로, 좌표계 변환에 맞춰 함께 변환된다.
- **Left-handed 좌표계 미지원**: Phase 2에서는 Right-handed 좌표계만 지원한다.
- **Attribute 처리**:
  - `POINT`, `EDGE`, `FACE`, `CORNER` domain attribute를 낸 장한다.
  - 지원하는 Blender data type은 `FLOAT`, `INT`, `FLOAT2`, `FLOAT_VECTOR`, `FLOAT_COLOR`, `BYTE_COLOR`, `INT32_2D`이다.
  - `BYTE_COLOR`는 0~1 범위로 정규화된 `F32×4`로 저장한다.
  - `BOOLEAN`, `STRING`, `INT8`, `INT16_2D`, `QUATERNION`, `FLOAT4X4` 등 v0.0.1에서 지원하지 않는 타입은 걸러내고 경고를 출력한다.
  - `.`로 시작하는 hidden/internal attribute, `position`, `sharp_edge/face`, `freestyle_edge/face` 등은 기본적으로 제외한다.
  - 사용자는 `Excluded Attributes`에 쉼표로 구분된 이름 목록을 지정해 추가로 제외할 수 있다.
- **다중 오브젝트 익스포트**:
  - 선택된 메시 오브젝트를 한 번에 익스포트할 수 있다.
  - `Selection Only` 옵션을 끄면 씬의 모든 메시 오브젝트를 익스포트한다.
  - 비메시 오브젝트는 경고 후 무시한다.
- **메시 공유**:
  - 여러 오브젝트가 동일한 메시 데이터 블록을 참조하면 `meshes` 배열에 한 번만 기록하고, `objects[].index`로 공유한다.
- **출력 파일**: 사용자가 선택한 `.mattr.json` 경로를 기준으로 동일한 basename의 `.mattr.bin`을 생성한다.

## 테스트

- `tests/test_phase0.py`는 Blender 백그라운드 모드에서 Extension을 등록하고 Operator를 실행하는 smoke test다.
- `tests/test_phase1.py`는 Default Cube와 빈 메시를 익스포트하여 토폴로지와 binary 레이아웃을 검증한다.
- `tests/test_phase2.py`는 좌표계 변환 및 Object Transform 변환을 검증한다.
- `tests/test_phase3.py`는 UV map, vertex color, custom attribute 등 attribute 익스포트를 검증한다.
- `tests/test_phase4.py`는 다중 오브젝트 익스포트와 메시 공유를 검증한다.
- 실행 예시:

```bash
blender -b -P blender_mattr_exporter/tests/test_phase0.py
blender -b -P blender_mattr_exporter/tests/test_phase1.py
blender -b -P blender_mattr_exporter/tests/test_phase2.py
blender -b -P blender_mattr_exporter/tests/test_phase3.py
blender -b -P blender_mattr_exporter/tests/test_phase4.py
blender -b -P blender_mattr_exporter/tests/test_phase3.py
```
