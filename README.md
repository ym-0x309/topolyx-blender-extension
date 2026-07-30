# Topolyx Import/Export

[English(`en_US`)](/README.md) | [한국어(`ko_KR`)](/README_ko_KR.md)

![Topolyx Import/Export](/images/topolyx-wordmark-1280-640.png)

This is a Blender extension for exporting and importing Blender mesh data to and from the Topolyx format (`.tlyx`).
For more information about the format, please refer to [this repository](https://github.com/ym-0x309/topolyx).

- Topolyx format version: `v1.0.0` or higher
- Supported Blender versions: `5.1.0` or higher

## Key Features

- Preserves vertex, edge, face, and face corner topology
- Exports and imports `POINT`, `EDGE`, `FACE`, and `CORNER` domain attributes
- Handles object transforms and `meters_per_unit` scaling
- Support for multiple references to a single mesh data block
- Uses the Topolyx 1.0.0 fixed coordinate system (`+Z` up, `+Y` forward, right-handed, CCW)

## Installation

### Install via Blender Extensions

> [!TIP]
> We recommend installing using this method.

1. Edit > Preferences > Get Extensions
2. Search for `topolyx` in the search bar
3. Install `Topolyx Import/Export`

### Install from Disk

1. Download the [latest release](https://github.com/ym-0x309/topolyx_import_export/releases)
2. Edit > Preferences > Get Extensions > Install from Disk

## Usage

> [!IMPORTANT]
> - Export: `File > Export > Topolyx (.tlyx)`
> - Import: `File > Import > Topolyx (.tlyx)`

### Export

`File > Export > Topolyx (.tlyx)`

Export Options

- `Selection Only`: When enabled, only the mesh objects selected in the viewport are exported. When disabled, all mesh objects are exported.
- Coordinate System
  - `Meters per Unit`: Specifies how many meters correspond to a length of 1.0 in the scene. The default is 1.0.
- Attribute Options
  - `Exclude Hidden/Internal Attributes`: When enabled, skips attributes starting with `.` that are hidden or used only internally by Blender, as well as the `position` attribute stored in the topology metadata. When disabled, all attributes are saved.
  - `Excluded Attributes`: Enter attribute names separated by `,` to skip those attributes.
  - `Remove Semantic Prefix`: When enabled, this removes the semantic prefix when semantics are detected via the `Auto Assign Semantics` option below (e.g., the name `DIRECTION_my_attr` is changed to `my_attr`). When disabled, the prefix is not removed even if semantics are detected.
  - `Auto Assign Semantics`: When enabled, the software recognizes the prefixes `POSITION`, `DIRECTION`, `NORMAL`, `ROTATION`, `TANGENT`, and `COLOR` at the beginning of attribute names and automatically assigns semantics (e.g., a name like `DIRECTION_my_attr` is automatically assigned the `DIRECTION` semantic). When disabled, all attributes not stored in the topology metadata are assigned `NONE`.

### Import

`File > Import > Topolyx (.tlyx)`

Import Options

- `Import Attributes`: When enabled, attributes other than the file’s topology metadata are imported. When disabled, only the topology metadata is imported.

## Report a Bug

Please report bugs on the [Issues](https://github.com/ym-0x309/topolyx_import_export/issues) page.