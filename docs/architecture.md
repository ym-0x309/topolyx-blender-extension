# MATTR Exporter Architecture

각 파일별 public API 시그니처와 역할을 정리한다. 세부 구현은 포함하지 않는다.

## `blender_manifest.toml`

- **역할**: Blender Extension 시스템이 인식하는 메타데이터 파일
- **주요 항목**:
  - `schema_version`: manifest 스키마 버전
  - `id`: Extension 고유 식별자
  - `name`, `version`, `maintainer`, `type`, `tags`
  - `blender_version_min`: 지원 최소 Blender 버전
  - `license`: 라이선스

## `__init__.py`

- **역할**: Extension의 진입점. Blender가 활성화/비활성화할 때 호출하는 `register()` / `unregister()`를 제공한다.

### Public API

```python
classes: list[type]
```
- 등록할 Operator 및 PropertyGroup 클래스 목록

```python
def menu_func(layout: bpy.types.UILayout, context: bpy.types.Context) -> None
```
- `File > Export` 메뉴에 Operator 항목을 추가한다.

```python
def register() -> None
```
- `classes`에 있는 모든 클래스를 Blender에 등록하고, 메뉴 항목을 추가한다.

```python
def unregister() -> None
```
- 메뉴 항목을 제거하고, 등록된 클래스를 역순으로 해제한다.

## `mattr_export_operator.py`

- **역할**: 사용자가 `File > Export` 메뉴를 통해 익스포트를 실행할 때 동작하는 Operator를 정의한다.

### Public API

```python
class MATTR_OT_export_mesh(bpy.types.Operator, ExportHelper)
```

- **Operator 식별자**: `export_mesh.mattr`
- **레이블**: `Export MATTR`
- **파일 확장자**: `.mattr.json`

#### 클래스 속성

| 이름 | 타입 | 역할 |
|------|------|------|
| `bl_idname` | `str` | Operator 고유 ID |
| `bl_label` | `str` | UI에 표시되는 이름 |
| `filename_ext` | `str` | 기본 파일 확장자 |
| `filter_glob` | `StringProperty` | 파일 대화상자 필터 |
| `use_setting` | `BoolProperty` | 예시 옵션(향후 확장용) |

#### 메서드

```python
def execute(self, context: bpy.types.Context) -> set[str]
```
- 선택된 오브젝트와 설정을 기반으로 익스포트를 수행한다.
- 성공 시 `{'FINISHED'}`를 반환한다.

## `mattr_properties.py`

- **역할**: 익스포트 옵션을 저장하는 `PropertyGroup`을 정의한다. Phase 0에서는 빈 그룹으로 등록만 되어 있다.

### Public API

```python
class MATTR_PG_export_settings(bpy.types.PropertyGroup)
```

- Blender의 PropertyGroup 메커니즘을 통해 익스포트 UI 옵션을 노출할 수 있는 컨테이너다.
- 향후 attribute 필터, 좌표계 옵션 등이 추가될 예정이다.

## `mattr_writer.py`

- **역할**: MATTR JSON 메타데이터와 binary 버퍼를 조립하여 파일 시스템에 쓴다.

### Public API

```python
def write_mattr(filepath: str) -> None
```

- **입력**: 사용자가 선택한 `.mattr.json` 파일 경로
- **동작**: 동일한 basename을 가진 `.mattr.json`과 `.mattr.bin`을 생성한다.
- **반환**: 없음

## `tests/test_phase0.py`

- **역할**: Blender 백그라운드 모드에서 Extension 등록과 Operator 호출을 검증하는 smoke test다.

### Public API

```python
def main() -> None
```

- Extension을 등록한다.
- 임시 디렉터리에 `.mattr.json` 경로를 지정하여 Operator를 호출한다.
- Operator가 `{'FINISHED'}`를 반환하는지 검증한다.
