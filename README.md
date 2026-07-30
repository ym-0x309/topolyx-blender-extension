# Topolyx Import/Export

[English(`en_US`)](/README.md) | [한국어(`ko_KR`)](/README_ko_KR.md)

This is a Blender extension for exporting and importing Blender mesh data to and from the Topolyx format (`.tlyx`).
For more information about the format, please refer to [this repository](https://github.com/ym-0x309/topolyx).

- Topolyx format version: `v1.0.0` or higher
- Supported Blender versions: `5.1.0` or higher

## Key Features

- Preserves vertex, edge, face, and face corner topology
- Exports and imports `POINT`, `EDGE`, `FACE`, and `CORNER` domain attributes
- Handles object transforms and `meters_per_unit` scaling
- Shares the same mesh data block
- Uses the Topolyx 1.0.0 fixed coordinate system (`+Z` up, `+Y` forward, right-handed, CCW)

## Installation

Since it is not yet listed on [extensions.blender.org](https://extensions.blender.org), you must install it manually.

1. Download the [latest release](https://github.com/ym-0x309/topolyx_import_export/releases)
2. Edit > Preferences > Get Extensions > Install from Disk

## Usage

- Export: `File > Export > Topolyx (.tlyx)`
- Import: `File > Import > Topolyx (.tlyx)`

## Report a Bug

Please report bugs on the [Issues](https://github.com/ym-0x309/topolyx_import_export/issues) page.