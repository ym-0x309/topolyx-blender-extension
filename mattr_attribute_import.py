"""Restore MATTR attributes onto a Blender Mesh data block."""

import array
from typing import List, Optional, Sequence

import bpy

from .mattr_attribute import (
    _SUPPORTED_DOMAINS,
    mattr_component_type_to_blender,
)
from .mattr_binary import BinaryBufferReader
from .mattr_types import Attribute, DataDescriptor


# MATTR domain -> Blender Mesh element collection attribute name
_DOMAIN_MESH_COLLECTION = {
    "POINT": "vertices",
    "EDGE": "edges",
    "FACE": "polygons",
    "CORNER": "loops",
}


# Attributes that conflict with Blender internal/reserved names.
# sharp_edge/face, freestyle_edge/face는 v0.2.0부터 정규 attribute로 다룬다.
_RESERVED_ATTRIBUTE_NAMES = {
    "position",
    "material_index",
    "normal",
    "shade_smooth",
}

_IMPORT_NAME_PREFIX = "import_"


def apply_attributes(
    mesh: bpy.types.Mesh,
    attributes: Sequence[Attribute],
    bin_data: bytes,
    warnings: Optional[List[str]] = None,
) -> List[str]:
    """Apply MATTR attributes to an existing Blender Mesh.

    U32 attributes are reinterpreted as signed 32-bit integers bit-for-bit,
    because Blender has no unsigned 32-bit attribute type. This is intentional.

    Args:
        mesh: Blender Mesh with topology already built.
        attributes: MATTR attributes to restore.
        bin_data: raw binary buffer.
        warnings: optional existing warnings list.

    Returns:
        list of warning messages.
    """
    warnings = warnings or []
    reader = BinaryBufferReader(bin_data)
    used_names: set[str] = set()

    for attr in attributes:
        warning = _apply_single_attribute(mesh, attr, reader, used_names)
        if warning:
            warnings.append(warning)

    mesh.update()
    return warnings


def _apply_single_attribute(
    mesh: bpy.types.Mesh,
    attr: Attribute,
    reader: BinaryBufferReader,
    used_names: set[str],
) -> Optional[str]:
    """Restore one MATTR attribute. Returns a warning message or None."""
    name = attr.name
    domain = attr.domain

    if domain not in _SUPPORTED_DOMAINS:
        return f"Skipping attribute '{name}': unsupported domain '{domain}'"

    try:
        blender_type, prop_name = mattr_component_type_to_blender(
            attr.data.component_type,
            attr.data.component_count,
        )
    except ValueError as exc:
        return f"Skipping attribute '{name}': {exc}"

    try:
        values = _read_attribute_values(reader, attr.data)
    except ValueError as exc:
        return f"Skipping attribute '{name}': {exc}"

    domain_collection = getattr(mesh, _DOMAIN_MESH_COLLECTION[domain])
    expected_count = len(domain_collection)
    actual_count = len(values) // attr.data.component_count
    if actual_count != expected_count:
        return (
            f"Skipping attribute '{name}': element count mismatch "
            f"({actual_count} vs {expected_count})"
        )

    resolved_name, rename_warning = _resolve_attribute_name(name, used_names)

    try:
        blender_attr = mesh.attributes.new(resolved_name, blender_type, domain)
    except Exception as exc:
        return f"Skipping attribute '{name}': failed to create attribute ({exc})"

    try:
        blender_attr.data.foreach_set(prop_name, values)
    except Exception as exc:
        return f"Skipping attribute '{resolved_name}': failed to write values ({exc})"

    return rename_warning


def _read_attribute_values(reader: BinaryBufferReader, desc: DataDescriptor):
    """Read raw attribute values from binary buffer.

    U32 values are bit-cast to signed 32-bit integers.
    """
    count = desc.element_count * desc.component_count
    if desc.component_type == "F32":
        return reader.read_f32(desc.byte_offset, count)
    elif desc.component_type == "I32":
        return reader.read_i32(desc.byte_offset, count)
    elif desc.component_type == "U32":
        return _read_u32_as_i32(reader, desc.byte_offset, count)
    elif desc.component_type == "BOOL":
        return reader.read_bool(desc.byte_offset, count)
    else:
        raise ValueError(f"Unsupported component type: {desc.component_type}")


def _read_u32_as_i32(reader: BinaryBufferReader, offset: int, count: int):
    """Read U32 values and reinterpret the bit pattern as signed I32.

    Blender has no unsigned 32-bit attribute type, so U32 attributes are stored
    as signed INT/INT32_2D with the same underlying bit pattern.
    """
    u32_values = reader.read_u32(offset, count)
    i32_values = array.array("i")
    i32_values.frombytes(u32_values.tobytes())
    return i32_values


def _resolve_attribute_name(name: str, used_names: set[str]) -> tuple[str, Optional[str]]:
    """Avoid collisions with reserved names and previously imported attributes.

    Returns:
        (resolved_name, warning): resolved_name is the safe name to use in Blender.
        warning is None if no rename occurred, otherwise a user-facing message.
    """
    warning: Optional[str] = None
    if name.startswith(".") or name.lower() in _RESERVED_ATTRIBUTE_NAMES:
        resolved = _IMPORT_NAME_PREFIX + name
        warning = f"Attribute '{name}' renamed to '{resolved}' to avoid reserved name collision"
    else:
        resolved = name

    while resolved in used_names or resolved.lower() in _RESERVED_ATTRIBUTE_NAMES:
        resolved = _IMPORT_NAME_PREFIX + resolved
        warning = f"Attribute '{name}' renamed to '{resolved}' to avoid name collision"

    used_names.add(resolved)
    return resolved, warning
