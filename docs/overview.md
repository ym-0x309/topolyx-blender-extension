# MATTR Exporter Overview

## Purpose

`MATTR Exporter` is a Blender Extension (add-on) for exporting Blender mesh data to the `MATTR` (Mesh Attribute & Topology Transfer Representation) format.

It targets Blender 5.1 and later, and aims to store mesh topology (positions, edges, faces, corners) and POINT/EDGE/FACE/CORNER domain attributes losslessly as a `.mattr.json` + `.mattr.bin` file pair.

This extension implements MATTR format version `v0.1.0`.

## File Structure

```text
blender_mattr_exporter/
├── blender_manifest.toml       # Extension metadata and Blender compatibility
├── __init__.py                 # Add-on registration/deregistration and menu wiring
├── mattr_export_operator.py    # File save dialog and export Operator
├── mattr_writer.py             # JSON + binary assembly entry point
├── mattr_reader.py             # JSON + binary load and validation entry point
├── mattr_types.py              # MATTR format data model
├── mattr_mesh.py               # Blender Mesh -> MATTR topology extraction
├── mattr_mesh_import.py        # MATTR topology -> Blender Mesh reconstruction
├── mattr_attribute.py          # Blender Mesh Attribute -> MATTR attribute conversion
├── mattr_attribute_import.py   # MATTR attribute -> Blender Mesh Attribute restoration
├── mattr_binary.py             # 4-byte aligned binary buffer builder/reader
├── mattr_coordinate.py         # Bidirectional coordinate system conversion
├── mattr_utils.py              # Shared utilities (matrix serialization, etc.)
├── mattr_validator.py          # Output file validation
├── mattr_importer.py           # End-to-end import entry point
├── mattr_import_operator.py    # File open dialog and import Operator
└── tests/
    ├── common.py               # Common test helpers
    ├── run_all.py              # Phase 0~9 integrated test runner
    ├── test_phase0.py          # Extension registration / Operator smoke test
    ├── test_phase1.py          # Topology export validation
    ├── test_phase2.py          # Coordinate system and Object Transform validation
    ├── test_phase3.py          # Attribute export validation
    ├── test_phase4.py          # Multi-object and mesh sharing validation
    ├── test_phase5.py          # Edge cases and validation strengthening
    ├── test_phase6.py          # Shared utilities and reader validation
    ├── test_phase7.py          # Topology import validation
    ├── test_phase8.py          # Attribute import validation
    └── test_phase9.py          # End-to-end importer validation
```

## Extension Lifecycle

### 1. Installation and Activation

- The user installs the directory containing `blender_manifest.toml` into Blender.
- When activated, Blender calls `register()` in `__init__.py`.

### 2. Registration

`register()` registers the following with Blender:

- `MATTR_OT_export_mesh` Operator
- `MATTR_OT_import_mesh` Operator
- `File > Export > MATTR (.mattr.json)` menu item
- `File > Import > MATTR (.mattr.json)` menu item

### 3. Export Usage Flow

1. The user selects `File > Export > MATTR (.mattr.json)`.
2. The Operator, inheriting from `ExportHelper`, opens the file save dialog.
3. The user chooses a path and presses Export.
4. The Operator's `execute()` is called and passes the target mesh object list to `mattr_writer`.
5. `mattr_writer` creates `.mattr.json` and `.mattr.bin` based on each object's `obj.data`. The same mesh data block is written only once.
6. After writing, `mattr_validator` validates the output files.

### 4. Import Usage Flow

1. The user selects `File > Import > MATTR (.mattr.json)`.
2. The Operator, inheriting from `ImportHelper`, opens the file open dialog.
3. The user chooses a `.mattr.json` file and presses Import.
4. The Operator's `execute()` is called and invokes `mattr_importer.import_mattr()`.
5. `mattr_importer` reads the file pair, reconstructs Blender meshes, restores attributes, and creates objects in the active collection.
6. Imported objects are selected and the last one is made active.

### 5. Deactivation

- When deactivated, Blender calls `unregister()`.
- It removes the registered Operators and menu items.

## Key Design Decisions

- **Original mesh usage**: Exports the original `obj.data` data block, not the evaluated mesh.
- **Coordinate system**: Exports to the MATTR v0.1.0 example coordinate system (`+Z` Up, `+Y` Forward, Right-handed, CCW). The `BLENDER` preset produces output identical to Blender's native coordinate system.
- **Object Transform conversion**: `object.transform` is the matrix that converts mesh local space coordinates to file world space coordinates, transformed according to the selected coordinate system.
- **Left-handed coordinate system not supported**: Only right-handed coordinate systems are supported.
- **Bidirectional conversion support**: `mattr_coordinate.py` provides inverse coordinate conversion to prepare for future importer implementation.
- **Attribute handling**:
  - Exports `POINT`, `EDGE`, `FACE`, `CORNER` domain attributes.
  - Supported Blender data types are `FLOAT`, `INT`, `FLOAT2`, `FLOAT_VECTOR`, `FLOAT_COLOR`, `BYTE_COLOR`, `INT32_2D`.
  - `BYTE_COLOR` is stored as normalized `F32×4` in the 0~1 range.
  - Types not supported in v0.1.0 such as `BOOLEAN`, `STRING`, `INT8`, `INT16_2D`, `QUATERNION`, `FLOAT4X4` are filtered out with warnings.
  - Hidden/internal attributes starting with `.`, `position`, `sharp_edge/face`, `freestyle_edge/face`, etc. are excluded by default.
  - Users can specify additional names to skip in the `Excluded Attributes` comma-separated list.
- **Multi-object export**:
  - Selected mesh objects can be exported at once.
  - Turning off `Selection Only` exports all mesh objects in the scene.
  - Non-mesh objects are skipped with a warning.
- **Mesh sharing**:
  - When multiple objects reference the same mesh data block, it is recorded once in the `meshes` array and shared via `objects[].index`.
- **Output files**: Generates a `.mattr.bin` with the same basename as the chosen `.mattr.json` path.
- **Self-validation**: Immediately after export, `mattr_validator` checks the output files and reports specification violations to the user.
- **Importer preparation**: Added `mattr_reader.py`, `BinaryBufferReader`, attribute reverse mapping, matrix deserialization utilities, `mattr_mesh_import.py` topology reconstruction, and `mattr_attribute_import.py` attribute restoration to lay the groundwork for future importer implementation.
- **Attribute import handling**:
  - Restores `POINT`, `EDGE`, `FACE`, `CORNER` domain attributes onto a Blender Mesh.
  - `U32` attributes are stored as signed `INT`/`INT32_2D` while preserving the underlying bit pattern, because Blender has no unsigned 32-bit attribute type.
  - Attribute names that conflict with Blender internal/reserved names are prefixed with `import_` and a warning is emitted.
- **Importer core**:
  - `mattr_importer.py` reads a MATTR file pair and creates Blender mesh objects in the active layer collection.
  - File-level mesh sharing is preserved when `apply_transform=False`.
  - `apply_transform=True` bakes the object world matrix into mesh vertices; shared meshes are duplicated so each object can be baked independently.
  - Imported objects are selected and the last one is made active.

## Tests

See [TESTING.md](TESTING.md) for detailed test execution instructions.

Summary:

```bash
blender -b -P blender_mattr_exporter/tests/run_all.py
```
