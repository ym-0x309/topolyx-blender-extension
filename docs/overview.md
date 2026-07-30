# Topolyx Import/Export Overview

## Purpose

`Topolyx Import/Export` is a Blender Extension (add-on) for importing and exporting Blender mesh data to the `Topolyx` (Mesh Attribute & Topology Transfer Representation) format.

It targets Blender 5.1 and later, and aims to store mesh topology (positions, edges, faces, corners) and POINT/EDGE/FACE/CORNER domain attributes losslessly as a single `.tlyx` file.

This extension implements Topolyx format version `v1.0.0`.

## File Structure

```text
topolyx_import_export/              # 프로젝트 루트
├── topolyx_import_export/          # Blender Extension(add-on) 패키지
│   ├── blender_manifest.toml       # Extension metadata and Blender compatibility
│   ├── __init__.py                 # Add-on registration/deregistration and menu wiring
│   ├── topolyx_export_operator.py    # File save dialog and export Operator
│   ├── topolyx_writer.py             # JSON + binary assembly entry point
│   ├── topolyx_reader.py             # JSON + binary load and validation entry point
│   ├── topolyx_types.py              # Topolyx format data model
│   ├── topolyx_mesh.py               # Blender Mesh -> Topolyx topology extraction
│   ├── topolyx_mesh_import.py        # Topolyx topology -> Blender Mesh reconstruction
│   ├── topolyx_attribute.py          # Blender Mesh Attribute -> Topolyx attribute conversion
│   ├── topolyx_attribute_import.py   # Topolyx attribute -> Blender Mesh Attribute restoration
│   ├── topolyx_binary.py             # 4-byte aligned binary buffer builder/reader
│   ├── topolyx_coordinate.py         # Bidirectional coordinate system conversion
│   ├── topolyx_utils.py              # Shared utilities (matrix serialization, etc.)
│   ├── topolyx_validator.py          # Output file validation
│   ├── topolyx_importer.py           # End-to-end import entry point
│   ├── topolyx_import_operator.py    # File open dialog and import Operator
│   └── tests/
│       ├── common.py               # Common test helpers
│       ├── run_all.py              # Phase 0~9 integrated test runner
│       ├── test_phase0.py          # Extension registration / Operator smoke test
│       ├── test_phase1.py          # Topology export validation
│       ├── test_phase2.py          # Coordinate system and Object Transform validation
│       ├── test_phase3.py          # Attribute export validation
│       ├── test_phase4.py          # Multi-object and mesh sharing validation
│       ├── test_phase5.py          # Edge cases and validation strengthening
│       ├── test_phase6.py          # Shared utilities and reader validation
│       ├── test_phase7.py          # Topology import validation
│       ├── test_phase8.py          # Attribute import validation
│       └── test_phase9.py          # End-to-end importer validation
├── docs/
├── README.md
└── LICENSE
```

## Extension Lifecycle

### 1. Installation and Activation

- The user installs the `topolyx_import_export/` directory containing `blender_manifest.toml` into Blender.
- When activated, Blender calls `register()` in `__init__.py`.

### 2. Registration

`register()` registers the following with Blender:

- `TOPOLYX_OT_export_mesh` Operator
- `TOPOLYX_OT_import_mesh` Operator
- `File > Export > Topolyx (.tlyx)` menu item
- `File > Import > Topolyx (.tlyx)` menu item

### 3. Export Usage Flow

1. The user selects `File > Export > Topolyx (.tlyx)`.
2. The Operator, inheriting from `ExportHelper`, opens the file save dialog.
3. The user chooses a path and presses Export.
4. The Operator's `execute()` is called and passes the target mesh object list to `topolyx_writer`.
5. `topolyx_writer` creates a single `.tlyx` file based on each object's `obj.data`. The same mesh data block is written only once.
6. After writing, `topolyx_validator` validates the output file.

### 4. Import Usage Flow

1. The user selects `File > Import > Topolyx (.tlyx)`.
2. The Operator, inheriting from `ImportHelper`, opens the file open dialog.
3. The user chooses a `.tlyx` file and presses Import.
4. The Operator's `execute()` is called and invokes `topolyx_importer.import_topolyx()`.
5. `topolyx_importer` reads the `.tlyx` file, reconstructs Blender meshes, restores attributes, and creates objects in the active collection.
6. Imported objects are selected and the last one is made active.

### 5. Deactivation

- When deactivated, Blender calls `unregister()`.
- It removes the registered Operators and menu items.

## Key Design Decisions

- **Original mesh usage**: Exports the original `obj.data` data block, not the evaluated mesh.
- **Coordinate system**: Exports to the Topolyx v1.0.0 fixed coordinate system (`+Z` Up, `+Y` Forward, Right-handed, CCW winding). The only configurable coordinate parameter is `meters_per_unit`. CW winding is not supported in v1.0.0.
- **Object Transform conversion**: `object.transform` is the matrix that converts mesh local space coordinates to file world space coordinates, scaled by `meters_per_unit`.
- **Left-handed coordinate system not supported**: Only the Topolyx v1.0.0 right-handed coordinate system is supported; importing a file with `handedness: LEFT` raises a validation error.
- **Bidirectional conversion support**: `topolyx_coordinate.py` provides inverse coordinate conversion (identity rotation plus `meters_per_unit` scaling) for the importer.
- **Attribute handling**:
  - Exports `POINT`, `EDGE`, `FACE`, `CORNER` domain attributes.
  - Supported Blender data types are `FLOAT`, `INT`, `INT8`, `FLOAT2`, `FLOAT_VECTOR`, `FLOAT_COLOR`, `BYTE_COLOR`, `INT32_2D`, `BOOLEAN`.
  - `BYTE_COLOR` is stored as `U8×4` with `semantic=COLOR`.
  - `BOOLEAN` is stored as `BOOL×1` (1 byte per element, `0`/`1`).
  - `INT8` is stored as `I8×1`.
  - Types not supported in v1.0.0 such as `STRING`, `INT16_2D`, `QUATERNION`, `FLOAT4X4` are filtered out with warnings.
  - Hidden/internal attributes starting with `.` and the topology-reserved name `position` are excluded by default. `sharp_edge/face` and `freestyle_edge/face` are exported as regular boolean attributes.
  - Users can specify additional names to skip in the `Excluded Attributes` comma-separated list.
  - Each attribute now carries a `semantic` field (`POSITION`, `DIRECTION`, `NORMAL`, `ROTATION`, `TANGENT`, `COLOR`, `NONE`). Semantic assignment uses built-in name heuristics (`normal`→`NORMAL`, `tangent`→`TANGENT`, `Col`/`color`→`COLOR`) plus name prefixes such as `DIRECTION_my_attribute`. The optional `Remove Semantic Prefix` setting strips the prefix from the exported name. The `Auto Assign Semantics` toggle enables or disables the entire detection; when a detected semantic does not match the attribute's actual `(component_type, component_count)`, it falls back to `NONE` so the exported file stays valid.
  - Attributes with coordinate-transform semantics (`POSITION`, `DIRECTION`, `NORMAL`, `ROTATION`, `TANGENT`) are converted to/from the target coordinate system during export/import.
- **Multi-object export**:
  - Selected mesh objects can be exported at once.
  - Turning off `Selection Only` exports all mesh objects in the scene.
  - Non-mesh objects are skipped with a warning.
- **Mesh sharing**:
  - When multiple objects reference the same mesh data block, it is recorded once in the `meshes` array and shared via `objects[].index`.
- **Output files**: Generates a single `.tlyx` file containing both JSON metadata and binary data chunks.
- **Self-validation**: Immediately after export, `topolyx_validator` checks the output files and reports specification violations to the user.
- **Importer preparation**: Added `topolyx_reader.py`, `BinaryBufferReader`, attribute reverse mapping, matrix deserialization utilities, `topolyx_mesh_import.py` topology reconstruction, and `topolyx_attribute_import.py` attribute restoration to lay the groundwork for future importer implementation.
- **Attribute import handling**:
  - Restores `POINT`, `EDGE`, `FACE`, `CORNER` domain attributes onto a Blender Mesh.
  - `U32` attributes are stored as signed `INT`/`INT32_2D` while preserving the underlying bit pattern, because Blender has no unsigned 32-bit attribute type.
  - `U8×4` attributes are restored as `BYTE_COLOR`.
  - `I8×1` attributes are sign-extended and stored as `INT`.
  - Attribute names that conflict with Blender internal/reserved names are prefixed with `import_` and a warning is emitted.
  - Coordinate-transform semantics are inverted so that imported attributes align with Blender's coordinate system.
- **Importer core**:
  - `topolyx_importer.py` reads a single Topolyx `.tlyx` file and creates Blender mesh objects in the active layer collection.
  - File-level mesh sharing is preserved across imported objects.
  - Imported objects are selected and the last one is made active.

## Tests

See [TESTING.md](TESTING.md) for detailed test execution instructions.

Summary:

```bash
blender -b -P topolyx_import_export/tests/run_all.py
```
