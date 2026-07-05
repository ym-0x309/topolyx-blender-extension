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
├── mattr_binary.py             # 4바이트 정렬 binary 버퍼 빌더
├── mattr_validator.py          # 출력 파일 유효성 검증
└── tests/
    ├── test_phase0.py          # Blender 낸 장기능 smoke test
    └── test_phase1.py          # 토폴로지 익스포트 검증
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
4. Operator의 `execute()`가 호출되고, active mesh 오브젝트를 `mattr_writer`에 전달한다.
5. `mattr_writer`는 `obj.data`를 기반으로 `.mattr.json`과 `.mattr.bin`을 생성한다.

### 4. 비활성화

- Blender는 비활성화 시 `unregister()`를 호출한다.
- 등록된 Operator, PropertyGroup, 메뉴 항목을 모두 제거한다.

## 주요 설계 결정

- **원본 메시 사용**: 평가된 메시(evaluated mesh)가 아닌 `obj.data` 원본 데이터 블록을 낸 장한다.
- **Blender 기본 좌표계**: Blender의 기본 좌표계(`+Z` Up, `+Y` Forward, Right-handed, CCW)를 그대로 사용한다. 별도의 축 변환은 수행하지 않는다.
- **Attribute 처리**: Blender 메시의 모든 attribute를 순회하여 낸 장한다. 단, `MATTR v0.0.1`이 지원하지 않는 component type(예: `BOOLEAN`, `BYTE_COLOR`, `STRING` 등)은 걸러낸다.
- **출력 파일**: 사용자가 선택한 `.mattr.json` 경로를 기준으로 동일한 basename의 `.mattr.bin`을 생성한다.

## 테스트

- `tests/test_phase0.py`는 Blender 백그라운드 모드에서 Extension을 등록하고 Operator를 실행하는 smoke test다.
- `tests/test_phase1.py`는 Default Cube와 빈 메시를 익스포트하여 토폴로지와 binary 레이아웃을 검증한다.
- 실행 예시:

```bash
blender -b -P blender_mattr_exporter/tests/test_phase0.py
blender -b -P blender_mattr_exporter/tests/test_phase1.py
```
