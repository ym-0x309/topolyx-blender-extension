# Topolyx Import/Export Architecture

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
- 등록할 Operator 클래스 목록

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

## `topolyx_export_operator.py`

- **역할**: 사용자가 `File > Export` 메뉴를 통해 익스포트를 실행할 때 동작하는 Operator를 정의한다.

### Public API

```python
class TOPOLYX_OT_export_mesh(bpy.types.Operator, ExportHelper)
```

- **Operator 식별자**: `export_mesh.tlyx`
- **레이블**: `Export Topolyx`
- **파일 확장자**: `.tlyx`

#### 클래스 속성

| 이름 | 타입 | 역할 |
|------|------|------|
| `bl_idname` | `str` | Operator 고유 ID |
| `bl_label` | `str` | UI에 표시되는 이름 |
| `filename_ext` | `str` | 기본 파일 확장자 |
| `filter_glob` | `StringProperty` | 파일 대화상자 필터 |
| `use_selection` | `BoolProperty` | `True`면 선택된 오브젝트만, `False`면 씬의 모든 메시 오브젝트 익스포트 |
| `meters_per_unit` | `FloatProperty` | 좌표계에서 1단위가 의미하는 미터 값 |
| `export_attributes` | `BoolProperty` | attribute 익스포트 여부 |
| `exclude_hidden_attributes` | `BoolProperty` | 낶부 Outputplus/internal attribute 제외 여부 |
| `excluded_attribute_names` | `StringProperty` | 추가 제외할 attribute 이름 목록 |
| `remove_semantic_prefix` | `BoolProperty` | semantic prefix를 attribute 이름에서 제거 |
| `auto_assign_semantics` | `BoolProperty` | 표준 이름/접두사에서 semantic 자동 할당 여부 |

#### 메서드

```python
def check(self, context: bpy.types.Context) -> bool
```
- `ExportHelper`의 기본 `check()`를 오버라이드하여 `.tlyx` 확장자가 중복되지 않도록 filepath를 보정한다.

```python
def draw(self, context: bpy.types.Context) -> None
```
- 파일 저장 대화상자 왼쪽 패널에 옵션을 그린다.

```python
def execute(self, context: bpy.types.Context) -> set[str]
```
- 선택된 오브젝트와 설정을 기반으로 익스포트를 수행한다.
- 익스포트 중 발생한 경고를 수집하여 UI에 리포트한다.
- 익스포트 완료 후 `topolyx_validator.validate_topolyx_file()`로 출력을 검증한다.
- 성공 시 `{'FINISHED'}`를 반환한다.

## `topolyx_writer.py`

- **역할**: Topolyx JSON 메타데이터와 binary 버퍼를 조립하여 파일 시스템에 쓴다.

### Public API

```python
def write_topolyx(
    filepath: str,
    objects: Sequence[bpy.types.Object],
    coordinate_system: CoordinateSystem,
    export_attributes: bool = True,
    exclude_hidden_attributes: bool = True,
    excluded_attribute_names: str = "",
    remove_semantic_prefix: bool = False,
    auto_assign_semantics: bool = True,
) -> List[str]
```

- **입력**:
  - `filepath`: 사용자가 선택한 `.tlyx` 파일 경로
  - `objects`: 낳볼 MESH 타입 Blender 오브젝트 목록
  - `coordinate_system`: `CoordinateSystem` 객체 형태의 목표 좌표계
  - `remove_semantic_prefix`: semantic prefix를 attribute 이름에서 제거할지 여부
  - `export_attributes`: attribute 낳볼내기 여부
  - `exclude_hidden_attributes`: 낮부 Outputplus/internal attribute 제외 여부
  - `excluded_attribute_names`: 쉼표로 구분된 추가 제외 attribute 이름
  - `auto_assign_semantics`: 표준 이름/접두사에서 semantic을 자동 할당할지 여부
- **동작**:
  - `.tlyx` 단일 파일을 생성한다.
  - `objects`를 순회하며 메시 데이터 블록을 기준으로 중복을 제거한다.
  - 동일한 메시를 참조하는 오브젝트는 `meshes` 배열에서 한 번만 기록된다.
- **반환**: 내보내는 중 발생한 경고 메시지 목록

```python
def _append_mesh(
    buffer: BinaryBuffer,
    mesh_name: str,
    topology_data: TopologyData,
    attribute_arrays: Sequence[AttributeArrays],
    converter: CoordinateConverter,
) -> Mesh
```

- 하나의 메시에 대해 topology 5종 배열과 일반 attribute 배열을 `BinaryBuffer`에 추가한다.
- attribute 값은 semantic에 따라 `converter`를 통해 좌표계 변환된다.
- 추가된 배열의 descriptor를 포함하는 `Mesh` 객체를 반환한다.

## `topolyx_reader.py`

- **역할**: Topolyx `.tlyx` 단일 파일을 읽어 `TopolyxFile` 데이터 모델과 raw binary bytes로 복원한다.

### Public API

```python
def read_topolyx(filepath: str | Path) -> Tuple[TopolyxFile, bytes]
```

- `.tlyx` 컨테이너 파일을 읽어 JSON 청크와 BIN 청크를 분리한다.
- `topolyx_validator.validate_topolyx()`로 검증한 후 `TopolyxFile.from_dict()`를 통해 파싱한다.
- 검증 실패 시 `TopolyxValidationError`를 발생시킨다.

```python
def read_topolyx_from_data(json_data: dict, bin_data: bytes) -> TopolyxFile
```

- 이미 메모리에 로드된 JSON dict와 binary bytes에서 `TopolyxFile`을 생성한다.
- `validate_topolyx()`을 먼저 호출한다.

## `topolyx_importer.py`

- **역할**: `TopolyxFile` 데이터를 Blender 씬의 메시 오브젝트로 복원한다.

### Public API

```python
class TopolyxImportError(Exception)
```

- import 중 치명적 오류 발생 시 발생하는 예외.

```python
def import_topolyx(
    filepath: str | Path,
    import_attributes: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[str]
```

- Topolyx 파일을 읽어 Blender 씬으로 import한다.
- `import_attributes=False`이면 attribute 복원을 건다.
- `(current_step, total_steps)`를 전달하는 progress_callback을 선택적으로 받는다.
- 복원 중 발생한 경고 메시지 목록을 반환한다.

### Internal helpers

- `_build_mesh()`: `TopolyxFile.meshes[]` 항목 하나를 Blender `Mesh`로 변환
- `_create_object()`: `TopolyxFile.objects[]` 항목 하나를 Blender `Object`로 생성 및 씬 링크
- `_cleanup_import()`: 실패 시 생성된 object/mesh 삭제

## `topolyx_import_operator.py`

- **역할**: `File > Import` 메뉴에서 실행되는 Blender Operator를 제공한다.

### Public API

```python
class TOPOLYX_OT_import_mesh(Operator, ImportHelper)
```

- **Operator 식별자**: `import_mesh.tlyx`
- **레이블**: `Import Topolyx`
- **파일 확장자**: `.tlyx`
- **bl_options**: `{"PRESET", "UNDO"}`

#### 클래스 속성

| 이름 | 타입 | 역할 |
|------|------|------|
| `bl_idname` | `str` | Operator 고유 ID |
| `bl_label` | `str` | UI에 표시되는 이름 |
| `filename_ext` | `str` | 기본 파일 확장자 |
| `filter_glob` | `StringProperty` | 파일 대화상자 필터 |
| `import_attributes` | `BoolProperty` | attribute 복원 여부 |

#### 메서드

```python
def draw(self, context: bpy.types.Context) -> None
```
- 파일 열기 대화상자 왼쪽 패널에 옵션을 그린다.

```python
def execute(self, context: bpy.types.Context) -> set[str]
```
- `topolyx_importer.import_topolyx()`를 호출하여 import를 수행한다.
- 진행률 표시줄을 업데이트한다.
- 발생한 경고를 UI와 콘솔에 노출한다.
- 성공 시 `{'FINISHED'}`를 반환한다.

## `topolyx_types.py`

- **역할**: Topolyx JSON을 표현하는 데이터 클래스(`DataDescriptor`, `Topology`, `Mesh`, `ObjectEntry`, `TopolyxFile` 등)를 정의한다.
- 각 dataclass는 `to_dict()`와 역직렬화용 `from_dict()`를 제공한다.

### Public API

```python
@dataclass
class DataDescriptor
```
- `byte_offset`, `byte_length`, `component_type`, `component_count`, `element_count`를 포함한다.
- `component_type`은 `"F32"`, `"I32"`, `"U32"`, `"I8"`, `"U8"`, `"BOOL"` 중 하나이다.

```python
@dataclass
class Topology
```
- 필수 메시 데이터 5종의 `DataDescriptor`를 묶는다.

```python
@dataclass
class TopolyxFile
```

- 전체 JSON 문서 루트. `to_dict()`로 dict로 변환한다.
- `header`, `coordinate_system`, `objects`, `meshes`를 포함한다.

```python
@dataclass
class Attribute
```

- 일반 attribute의 JSON 표현. `name`, `domain`, `semantic`, `data: DataDescriptor`를 포함한다.
- `semantic`은 `"POSITION"`, `"DIRECTION"`, `"NORMAL"`, `"ROTATION"`, `"TANGENT"`, `"COLOR"`, `"NONE"` 중 하나이며 기본값은 `"NONE"`이다.

```python
@dataclass
class Header
```

- `format`은 `"Topolyx"`, `version`은 `"1.0"`이다.

## `topolyx_mesh.py`

- **역할**: Blender `bpy.types.Mesh` 데이터 블록에서 Topolyx 필수 토폴로지 배열을 추출한다.

### Public API

```python
def extract_topology(mesh: bpy.types.Mesh, converter: CoordinateConverter) -> TopologyData
```
- `mesh.vertices`, `mesh.edges`, `mesh.polygons`, `mesh.loops`를 순회하여 flat 배열로 변환한다.
- `converter`를 통해 vertex positions는 target 좌표계로 변환된다.
- `face_offsets`는 `mesh.polygons`의 인덱스 순서를 따른다.
- 반환값에는 `element_counts`와 `positions`, `edges`, `corner_vertices`, `corner_edges`, `face_offsets`가 포함된다.

## `topolyx_mesh_import.py`

- **역할**: Topolyx topology 배열(positions, edges, corner_vertices, corner_edges, face_offsets)로 Blender `bpy.types.Mesh` 데이터 블록을 복원한다.

### Public API

```python
def build_blender_mesh(
    name: str,
    positions: Sequence[float],
    edges: Sequence[int],
    corner_vertices: Sequence[int],
    corner_edges: Sequence[int],
    face_offsets: Sequence[int],
) -> bpy.types.Mesh
```

- `from_pydata`를 사용하여 topology를 복원한다.
- Topolyx 1.0.0은 `winding=CCW`만 지원하므로, 별도의 reverse 로직은 없다.
- 생성 후 `mesh.loops[i].edge_index`가 `corner_edges[i]`와 일치하도록 강제한다.
- duplicate edge가 있으면 `ValueError`를 발생시킨다.

## `topolyx_attribute.py`

- **역할**: Blender `bpy.types.Mesh` 데이터 블록의 attribute를 Topolyx attribute로 변환한다.

### Public API

```python
@dataclass
class AttributeArrays
```

- Binary 직렬화 직전의 attribute 데이터. `name`, `domain`, `component_type`, `component_count`, `values`, `semantic`를 포함한다.

```python
def extract_attributes(
    mesh: bpy.types.Mesh,
    counts: ElementCounts,
    export_attributes: bool = True,
    exclude_hidden: bool = True,
    excluded_names: Optional[Set[str]] = None,
    remove_semantic_prefix: bool = False,
    auto_assign_semantics: bool = True,
) -> Tuple[List[AttributeArrays], List[str]]
```

- `mesh.attributes`를 순회하여 지원하는 attribute만 추출한다.
- 반환값은 `(attributes, warnings)` 튜플이다.
- 지원하는 Blender data type은 `FLOAT`, `INT`, `INT8`, `FLOAT2`, `FLOAT_VECTOR`, `FLOAT_COLOR`, `BYTE_COLOR`, `INT32_2D`, `BOOLEAN`이다.
- `BYTE_COLOR`는 `U8×4`로 저장하고 `semantic=COLOR`를 부여한다.
- `INT8`은 `I8×1`로 저장한다.
- `BOOLEAN`은 `BOOL×1`로 저장한다.
- `auto_assign_semantics=True`일 때, attribute 이름이나 data_type에 따라 `semantic`이 자동 할당되며, `DIRECTION_`, `POSITION_` 등의 prefix도 인식한다.
- 자동 할당된 semantic이 명세의 `(component_type, component_count)` 제약과 맞지 않으면 `NONE`으로 fallback한다.

```python
def topolyx_component_type_to_blender(
    component_type: str, component_count: int
) -> Tuple[str, str]
```

- TOPOLYX의 `(component_type, component_count)` 조합을 Blender의 `(data_type, prop_name)`으로 환산한다.
- `F32×4`는 `FLOAT_COLOR`로, `U8×4`는 `BYTE_COLOR`로 환산한다.
- `I8×1`은 `INT8`로 환산한다.
- `U32×1`과 `U32×2`는 Blender에 unsigned 32-bit attribute type이 없으므로, 비트 패턴을 그대로 유지한 채 `INT`/`INT32_2D`로 환산한다.
- `BOOL×1`은 `BOOLEAN`으로 환산한다.
- `INT32_2D`의 `foreach_get`/`foreach_set` property는 `"value"`이다.
- 지원하지 않는 조합이면 `ValueError`를 발생시킨다.

## `topolyx_attribute_import.py`

- **역할**: 이미 생성된 Blender `bpy.types.Mesh` 데이터 블록에 Topolyx attribute를 복원한다.

### Public API

```python
def apply_attributes(
    mesh: bpy.types.Mesh,
    attributes: Sequence[Attribute],
    bin_data: bytes,
    warnings: Optional[List[str]] = None,
    converter: Optional[CoordinateConverter] = None,
) -> List[str]
```

- `mesh`의 topology가 완성된 상태에서 호출한다.
- `BinaryBufferReader`로 binary를 읽고, `topolyx_component_type_to_blender()`로 Blender attribute type을 결정한다.
- `position`, `material_index` 등 Blender internal/reserved 이름과 충돌하는 이름은 `import_` prefix를 붙여 rename한다.
- U32 attribute는 비트 패턴을 그대로 I32로 해석하여 저장한다.
- U8×4 attribute는 `BYTE_COLOR`로, I8×1 attribute는 `INT8`로 복원한다.
- `converter`가 주어지면 coordinate-transform semantic (`POSITION`, `DIRECTION`, `ROTATION`, `TANGENT`) attribute 값을 Blender 좌표계로 역변환한다.
- 반환값은 경고 메시지 목록이다.

## `topolyx_coordinate.py`

- **역할**: Blender 좌표계와 Topolyx 목표 좌표계 사이를 양방향으로 변환하는 변환기를 제공한다.

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
- `"BLENDER"` 또는 `"TOPOLYX_DEFAULT"` preset으로 초기화한다.
- Right-handed 좌표계만 지원한다.

```python
@classmethod
def from_coordinate_system(cls, cs: CoordinateSystem) -> CoordinateConverter
```
- `CoordinateSystem` 객체로 변환기를 생성한다. Importer에서 파일의 `coordinate_system`을 직접 읽어올 때 사용한다.
- `meters_per_unit`에 따른 단위 스케일도 함께 처리한다.

```python
@property
def winding(self) -> str
```

- target 좌표계의 winding을 반환한다. Topolyx 1.0.0에서는 항상 `"CCW"`이다.

```python
def convert_position(self, v: Vector) -> Vector
```
- Blender local/world position을 target local/world position으로 변환한다.
- `meters_per_unit`에 따라 위치를 스케일한다.
```python
def convert_matrix(self, m: Matrix) -> Matrix
```

- Blender 4x4 world matrix를 target 4x4 world matrix로 변환한다.
- ``M_target = S^-1 @ M @ S``를 적용한다. (`S`는 `meters_per_unit` uniform scale)

```python
def inverse_convert_position(self, v: Vector) -> Vector
```
- target local/world position을 Blender local/world position으로 변환한다.

```python
def inverse_convert_matrix(self, m: Matrix) -> Matrix
```

- target 4x4 world matrix를 Blender 4x4 world matrix로 변환한다.
- ``M_blender = S @ M @ S^-1``를 적용한다.

```python
def convert_rotation(self, q: Quaternion) -> Quaternion
```
- Blender 쿼터니언 회전을 target 좌표계 쿼터니언으로 변환한다.

```python
def inverse_convert_rotation(self, q: Quaternion) -> Quaternion
```
- target 쿼터니언 회전을 Blender 좌표계 쿼터니언으로 변환한다.

```python
def convert_tangent(self, t: Vector) -> Vector
```
- Tangent 벡터 `(x, y, z, w)`를 target 좌표계로 변환한다.

```python
def inverse_convert_tangent(self, t: Vector) -> Vector
```
- target Tangent 벡터 `(x, y, z, w)`를 Blender 좌표계로 변환한다.

## `topolyx_utils.py`

- **역할**: 익스포터와 향후 임포터가 공유하는 작은 유틸리티 함수를 제공한다.

### Public API

```python
def matrix_to_column_major_list(matrix: Matrix) -> List[float]
```
- `mathutils.Matrix`를 column-major 순서의 16개 float list로 직렬화한다.

```python
def column_major_list_to_matrix(values: Sequence[float]) -> Matrix
```
- column-major 16개 float list를 `mathutils.Matrix`로 복원한다.
- 길이가 16이 아니면 `ValueError`를 발생시킨다.

## `topolyx_binary.py`

- **역할**: little-endian F32/I32/U32/I8/U8/BOOL 배열을 4바이트 정렬로 조립하는 binary 버퍼와, 기록된 버퍼를 읽는 reader를 제공한다.

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
def append_bool(self, values: Iterable[int]) -> int
```

- BOOL 배열을 1바이트씩 추가하고 시작 `byte_offset`을 반환한다.

```python
def append_i8(self, values: Sequence[int]) -> int
```

- I8 배열을 1바이트씩 추가하고 시작 `byte_offset`을 반환한다.

```python
def append_u8(self, values: Sequence[int]) -> int
```

- U8 배열을 1바이트씩 추가하고 시작 `byte_offset`을 반환한다.

```python
def byte_length(self) -> int
```
- 현재 버퍼의 총 byte 길이를 반환한다.

```python
def to_bytes(self) -> bytes
```
- 현재 버퍼의 내용을 `bytes`로 반환한다.

```python
def write(self, path: Path) -> None
```
- 버퍼 내용을 파일에 쓴다.

```python
class BinaryBufferReader
```

```python
def read_f32(self, offset: int, count: int) -> array.array
```
- 지정한 offset부터 count개의 F32 값을 읽어 반환한다.

```python
def read_i32(self, offset: int, count: int) -> array.array
```
- 지정한 offset부터 count개의 I32 값을 읽어 반환한다.
```python
def read_u32(self, offset: int, count: int) -> array.array
```

- 지정한 offset부터 count개의 U32 값을 읽어 반환한다.

```python
def read_bool(self, offset: int, count: int) -> array.array
```

- 지정한 offset부터 count개의 BOOL 값을 읽어 `array.array('b')`로 반환한다.

```python
def read_i8(self, offset: int, count: int) -> array.array
```

- 지정한 offset부터 count개의 I8 값을 읽어 `array.array('b')`로 반환한다.

```python
def read_u8(self, offset: int, count: int) -> array.array
```

- 지정한 offset부터 count개의 U8 값을 읽어 `array.array('B')`로 반환한다.

## `topolyx_validator.py`

- **역할**: Topolyx 출력 파일이 명세의 유효성 조건을 만족하는지 검증한다.

### Public API

```python
class TopolyxValidationError(Exception)
```

- 검증 실패 시 발생하는 예외.

```python
def validate_topolyx(json_data: Dict[str, Any], bin_data: bytes) -> None
```

- `header`, `buffer`, `coordinate_system`, `mesh` descriptor, 인덱스 범위, `face_offsets`, corner-edge 일관성을 검사한다.
- `header.version`의 major/minor 버전이 지원 버전(`1.0.0` → `1.0`)과 일치하는지 검사한다.
- `.tlyx` 컨테이너 구조(magic, version, total_length, 청크 타입/길이/패딩)를 검사한다.
- `coordinate_system`이 Topolyx v1.0.0 고정값(`+Z` up, `+Y` forward, `RIGHT`, `CCW`)을 따르는지 검사한다.
- `attributes`에 대해 이름 중복, domain, semantic, component_type, component_count, element_count, byte offset/length를 검사한다.
- descriptor의 `byte_offset`과 `byte_length`가 음수가 아닌지 검사한다.
- `coordinate_system.meters_per_unit`이 양의 유한수인지 검사한다.
- object/mesh/attribute 이름이 비어 있거나 잘못 중복되지 않는지 검사한다.
- object `transform`의 선형 부분이 비특이 행렬인지 검사한다.
- topology `edges`에 self-edge나 중복 edge가 없는지 검사한다.
- 조건을 만족하지 않으면 `TopolyxValidationError`를 발생시킨다.

```python
def validate_topolyx_file(filepath: Path) -> None
```

- `.tlyx` 단일 파일을 읽어 JSON 청크와 BIN 청크를 분리한 후 검증한다.

## `tests/common.py`

- **역할**: 테스트에서 공통으로 사용하는 헬퍼 함수 모음.

### Public API

```python
ADDON_MODULE: str
```
- 애드온 모듈 이름 `"topolyx_import_export"`.

```python
def reset_addon() -> module
```
- 소스 디렉터리의 애드온을 등록하고 반환한다.

```python
def clear_scene() -> None
```
- 현재 씬의 모든 오브젝트를 삭제한다.

```python
def select_only(objs: Sequence[bpy.types.Object]) -> None
```
- 지정한 오브젝트들만 선택하고 active를 마지막으로 설정한다.

```python
def export_active_object(tmpdir: Path, name: str, **operator_kwargs) -> Path
```
- active object를 익스포트하고 `.tlyx` 파일 경로를 반환한다.

```python
def export_selected(tmpdir: Path, name: str, **operator_kwargs) -> Path
```
- 선택된 오브젝트들을 익스포트하고 `.tlyx` 파일 경로를 반환한다.

```python
def export_all_meshes(tmpdir: Path, name: str, **operator_kwargs) -> Path
```
- 씬의 모든 메시 오브젝트를 익스포트하고 `.tlyx` 파일 경로를 반환한다.

```python
def load_result(tlyx_path: Path) -> tuple[dict, bytes]
```
- `.tlyx` 파일을 읽어 JSON과 binary를 분리한 후 `validate_topolyx`로 검증 후 반환한다.

```python
def find_attribute(data: dict, name: str, mesh_index: int = 0) -> dict
```
- 지정한 mesh의 attributes에서 이름으로 attribute를 찾는다.

```python
def find_object(data: dict, name: str) -> dict
```
- objects 배열에서 이름으로 object entry를 찾는다.

```python
def find_mesh(data: dict, name: str) -> dict
```
- meshes 배열에서 이름으로 mesh entry를 찾는다.

```python
def assert_f32_values(bin_data: bytes, desc: dict, expected: Sequence[float]) -> None
```
- binary에서 descriptor 위치의 F32 값이 expected와 일치하는지 확인한다.

```python
def assert_i32_values(bin_data: bytes, desc: dict, expected: Sequence[int]) -> None
```
- binary에서 descriptor 위치의 I32 값이 expected와 일치하는지 확인한다.

```python
def assert_u32_values(bin_data: bytes, desc: dict, expected: Sequence[int]) -> None
```
- binary에서 descriptor 위치의 U32 값이 expected와 일치하는지 확인한다.

```python
def tempdir() -> Path
```
- 테스트용 임시 디렉터리를 Path 객체로 반환한다.

```python
def import_topology_only(tlyx_path: Path) -> bpy.types.Mesh
```
- Topolyx `.tlyx` 파일에서 topology만 복원한 Blender Mesh 데이터 블록을 반환한다.
- Phase 7/8 테스트에서 mesh 생성 로직을 공유하기 위해 사용한다.

## `tests/run_all.py`

- **역할**: Blender 백그라운드 모드에서 Phase 0~9 테스트를 순차 실행하는 통합 러너.

### Public API

```python
def main() -> int
```

- Phase 0~8 테스트 모듈을 순차 실행한다.
- 모든 테스트가 통과하면 `0`, 실패하면 `1`을 반환한다.

## `tests/test_phase0.py`

- **역할**: Blender 백그라운드 모드에서 Extension 등록과 Operator 호출을 검증하는 smoke test.

## `tests/test_phase1.py`

- **역할**: Blender 백그라운드 모드에서 Default Cube 및 빈 메시의 토폴로지 익스포트를 검증.

## `tests/test_phase2.py`

- **역할**: Blender 백그라운드 모드에서 좌표계 변환 및 Object Transform 변환을 검증.

## `tests/test_phase3.py`

- **역할**: Blender 백그라운드 모드에서 attribute 익스포트를 검증.

## `tests/test_phase4.py`

- **역할**: Blender 백그라운드 모드에서 다중 오브젝트 익스포트와 메시 공유를 검증.

## `tests/test_phase5.py`

- **역할**: Blender 백그라운드 모드에서 N-gon, loose geometry, EDGE domain attribute, 다중 attribute, 음수 integer, 큰 좌표값 등 엣지 케이스와 validator 강화를 검증.

## `tests/test_phase6.py`

- **역할**: Blender 백그라운드 모드에서 양방향 좌표 변환, 행렬 직렬화/역직렬화, binary reader, attribute 역매핑, `topolyx_reader`를 검증.

## `tests/test_phase7.py`

- **역할**: Blender 백그라운드 모드에서 `topolyx_mesh_import.py`의 topology 복원 기능을 검증. Default Cube, 빈 메시, loose vertex/edge, N-gon, mixed face, CW winding reverse를 포함한다.

## `tests/test_phase8.py`

- **역할**: Blender 백그라운드 모드에서 `topolyx_attribute_import.py`의 attribute 복원 기능을 검증. POINT/EDGE/FACE/CORNER domain의 FLOAT, INT, FLOAT_COLOR, FLOAT2, INT32_2D attribute round-trip, 다중 attribute, 예약어 이름 rename, U32 bit-cast를 포함한다.

## `tests/test_phase9.py`

- **역할**: Blender 백그라운드 모드에서 `topolyx_importer.py`의 end-to-end import 기능을 검증. round-trip, 다중 오브젝트, shared mesh, apply_transform, empty mesh, attribute toggle, reserved name 처리를 포함한다.
