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
def menu_func(self: bpy.types.Menu, context: bpy.types.Context) -> None
```
- `File > Export` 메뉴에 Operator 항목을 추가한다.
- `self.layout.operator(...)` 형태로 항목을 그린다.

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
| `use_selection` | `BoolProperty` | `True`면 선택된 오브젝트만, `False`면 씬의 모든 메시 오브젝트 익스포트 |
| `coordinate_system_preset` | `EnumProperty` | `"BLENDER"` 또는 `"MATTR_DEFAULT"` 좌표계 선택 |
| `export_attributes` | `BoolProperty` | attribute 익스포트 여부 |
| `exclude_hidden_attributes` | `BoolProperty` | 난 Outputplus/internal attribute 제외 여부 |
| `excluded_attribute_names` | `StringProperty` | 추가 제외할 attribute 이름 목록 |

#### 메서드

```python
def check(self, context: bpy.types.Context) -> bool
```
- `ExportHelper`의 기본 `check()`를 오버라이드하여 `.mattr.json` 다중 확장자가 중복되지 않도록 filepath를 보정한다.

```python
def draw(self, context: bpy.types.Context) -> None
```
- 파일 저장 대화상자 왼쪽 패널에 좌표계 옵션을 그린다.

```python
def execute(self, context: bpy.types.Context) -> set[str]
```
- 선택된 오브젝트와 설정을 기반으로 익스포트를 수행한다.
- 성공 시 `{'FINISHED'}`를 반환한다.

## `mattr_properties.py`

- **역할**: 익스포트 옵션을 저장하는 `PropertyGroup`을 정의한다. Phase 2까지는 Operator에 직접 속성을 두고, 이 그룹은 확장용으로 등록만 되어 있다.

### Public API

```python
class MATTR_PG_export_settings(bpy.types.PropertyGroup)
```

- Blender의 PropertyGroup 메커니즘을 통해 익스포트 UI 옵션을 노출할 수 있는 컨테이너다.
- 향후 attribute 필터 등이 추가될 예정이다.

## `mattr_writer.py`

- **역할**: MATTR JSON 메타데이터와 binary 버퍼를 조립하여 파일 시스템에 쓴다.

### Public API

```python
def write_mattr(
    filepath: str,
    objects: Sequence[bpy.types.Object],
    coordinate_system_preset: str = "MATTR_DEFAULT",
    export_attributes: bool = True,
    exclude_hidden_attributes: bool = True,
    excluded_attribute_names: str = "",
) -> None
```

- **입력**:
  - `filepath`: 사용자가 선택한 `.mattr.json` 파일 경로
  - `objects`: 낸 장할 MESH 타입 Blender 오브젝트 목록
  - `coordinate_system_preset`: `"BLENDER"` 또는 `"MATTR_DEFAULT"`
  - `export_attributes`: attribute 낸 장 여부
  - `exclude_hidden_attributes`: 난 Outputplus/internal attribute 제외 여부
  - `excluded_attribute_names`: 쉼표로 구분된 추가 제외 attribute 이름
- **동작**:
  - 동일한 basename을 가진 `.mattr.json`과 `.mattr.bin`을 생성한다.
  - `objects`를 순회하며 메시 데이터 블록을 기준으로 중복을 제거한다.
  - 동일한 메시를 참조하는 오브젝트는 `meshes` 배열에서 한 번만 기록된다.
- **반환**: 없음

```python
def _append_mesh(
    buffer: BinaryBuffer,
    mesh_name: str,
    topology_data: TopologyData,
    attribute_arrays: Sequence[AttributeArrays],
) -> Mesh
```

- 하나의 메시에 대해 topology 5종 배열과 일반 attribute 배열을 `BinaryBuffer`에 추가한다.
- 추가된 배열의 descriptor를 포함하는 `Mesh` 객체를 반환한다.

## `mattr_types.py`

- **역할**: MATTR JSON을 표현하는 데이터 클래스(`DataDescriptor`, `Topology`, `Mesh`, `ObjectEntry`, `MattrFile` 등)를 정의한다.

### Public API

```python
@dataclass
class DataDescriptor
```
- `byte_offset`, `byte_length`, `component_type`, `component_count`, `element_count`를 포함한다.

```python
@dataclass
class Topology
```
- 필수 메시 데이터 5종의 `DataDescriptor`를 묶는다.
```python
@dataclass
class MattrFile
```

- 전체 JSON 문서 루트. `to_dict()`로 dict로 변환한다.

```python
@dataclass
class Attribute
```

- 일반 attribute의 JSON 표현. `name`, `domain`, `data: DataDescriptor`를 포함한다.

## `mattr_mesh.py`

- **역할**: Blender `bpy.types.Mesh` 데이터 블록에서 MATTR 필수 토폴로지 배열을 추출한다.

### Public API

```python
def extract_topology(mesh: bpy.types.Mesh, converter: CoordinateConverter) -> TopologyData
```
- `mesh.vertices`, `mesh.edges`, `mesh.polygons`, `mesh.loops`를 순회하여 flat 배열로 변환한다.
- `converter`를 통해 vertex positions는 target 좌표계로 변환된다.
- `face_offsets`는 `mesh.polygons`의 인덱스 순서를 따른다.
- 반환값에는 `element_counts`와 `positions`, `edges`, `corner_vertices`, `corner_edges`, `face_offsets`가 포함된다.

## `mattr_attribute.py`

- **역할**: Blender `bpy.types.Mesh` 데이터 블록의 attribute를 MATTR attribute로 변환한다.

### Public API

```python
@dataclass
class AttributeArrays
```

- Binary 직렬화 직전의 attribute 데이터. `name`, `domain`, `component_type`, `component_count`, `values`를 포함한다.

```python
def extract_attributes(
    mesh: bpy.types.Mesh,
    counts: ElementCounts,
    export_attributes: bool = True,
    exclude_hidden: bool = True,
    excluded_names: Optional[Set[str]] = None,
) -> Tuple[List[AttributeArrays], List[str]]
```

- `mesh.attributes`를 순회하여 지원하는 attribute만 추출한다.
- 반환값은 `(attributes, warnings)` 튜플이다.
- 지원하는 Blender data type은 `FLOAT`, `INT`, `FLOAT2`, `FLOAT_VECTOR`, `FLOAT_COLOR`, `BYTE_COLOR`, `INT32_2D`이다.
- `BYTE_COLOR`는 `F32×4`로 정규화한다.

## `mattr_coordinate.py`

- **역할**: Blender 좌표계에서 MATTR 목표 좌표계로 변환하는 변환기를 제공한다.

### Public API

```python
@dataclass
class CoordinateSystem
```
- `up_axis`, `forward_axis`, `handedness`, `winding`, `meters_per_unit`를 포함한다.

```python
class CoordinateConverter
```

```python
def __init__(self, preset: str) -> None
```
- `"BLENDER"` 또는 `"MATTR_DEFAULT"` preset으로 초기화한다.
- Right-handed 좌표계만 지원한다.

```python
def convert_position(self, v: Vector) -> Vector
```
- Blender local/world position을 target local/world position으로 변환한다.

```python
def convert_matrix(self, m: Matrix) -> Matrix
```
- Blender 4x4 world matrix를 target 4x4 world matrix로 변환한다.
- ``M_target = M_cs @ M_blender @ M_cs^-1``를 적용한다.

## `mattr_binary.py`

- **역할**: little-endian F32/U32 배열을 4바이트 정렬로 조립하는 binary 버퍼를 제공한다.

### Public API
```python
class BinaryBuffer
```

```python
def append_f32(self, values: Sequence[float]) -> int
```

- F32 배열을 추가하고 시작 `byte_offset`을 반환한다.

```python
def append_i32(self, values: Sequence[int]) -> int
```

- I32 배열을 추가하고 시작 `byte_offset`을 반환한다.

```python
def append_u32(self, values: Sequence[int]) -> int
```

- U32 배열을 추가하고 시작 `byte_offset`을 반환한다.
```python
def byte_length(self) -> int
```
- 현재 버퍼의 총 byte 길이를 반환한다.

```python
def write(self, path: Path) -> None
```
- 버퍼 내용을 파일에 쓴다.

## `mattr_validator.py`

- **역할**: MATTR 출력 파일이 명세의 유효성 조건을 만족하는지 검증한다.

### Public API

```python
def validate_mattr(json_data: Dict[str, Any], bin_data: bytes) -> None
```

- `header`, `buffer`, `coordinate_system`, `mesh` descriptor, 인덱스 범위, `face_offsets`, corner-edge 일관성을 검사한다.
- `attributes`에 대해 이름 중복, domain, component_type, component_count, element_count, byte offset/length를 검사한다.
- 조건을 만족하지 않으면 `AssertionError`를 발생시킨다.

## `tests/test_phase0.py`

- **역할**: Blender 백그라운드 모드에서 Extension 등록과 Operator 호출을 검증하는 smoke test다.

### Public API

```python
def main() -> None
```

- Extension을 등록한다.
- 임시 디렉터리에 `.mattr.json` 경로를 지정하여 Operator를 호출한다.
- Operator가 `{'FINISHED'}`를 반환하는지 검증한다.

## `tests/test_phase1.py`

- **역할**: Blender 백그라운드 모드에서 Default Cube 및 빈 메시의 토폴로지 익스포트를 검증하는 테스트다.

### Public API

```python
def main() -> None
```

- Extension을 등록한다.
- Default Cube와 빈 메시를 각각 익스포트한다.
- `mattr_validator.validate_mattr()`로 출력 파일을 검증하고, byte offset/length 및 element count를 확인한다.

## `tests/test_phase2.py`

- **역할**: Blender 백그라운드 모드에서 좌표계 변환 및 Object Transform 변환을 검증하는 테스트다.

### Public API

```python
def main() -> None
```

- Extension을 등록한다.
- Default Cube를 `MATTR_DEFAULT`와 `BLENDER` preset으로 각각 익스포트한다.
- `mattr_validator.validate_mattr()`로 출력 파일을 검증하고, 좌표계 및 transform을 확인한다.

## `tests/test_phase3.py`

- **역할**: Blender 백그라운드 모드에서 attribute 익스포트를 검증하는 테스트다.

### Public API

```python
def main() -> None
```

- Extension을 등록한다.
- Default Cube, custom float/int attribute, vertex color, UV map, 빈 메시 등을 익스포트한다.
- `mattr_validator.validate_mattr()`로 출력 파일을 검증하고, attribute descriptor 및 binary 값을 확인한다.

## `tests/test_phase4.py`

- **역할**: Blender 백그라운드 모드에서 다중 오브젝트 익스포트와 메시 공유를 검증하는 테스트다.

### Public API

```python
def main() -> None
```

- Extension을 등록한다.
- 서로 다른 메시를 가진 여러 오브젝트, 링크 복제로 공유된 메시, 선택/비선택 오브젝트, 비메시 오브젝트 스킵, 빈 메시 포함 등을 검증한다.
- `mattr_validator.validate_mattr()`로 출력 파일을 검증하고, `objects`/`meshes` 구조 및 `objects[].index` 공유를 확인한다.
