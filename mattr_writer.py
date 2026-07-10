"""Assemble and write MATTR JSON + binary file pairs."""

import json
from pathlib import Path
from typing import Callable, List, Optional, Sequence

import bpy

from . import mattr_attribute, mattr_binary, mattr_coordinate, mattr_mesh
from .mattr_coordinate import CoordinateConverter
from .mattr_types import (
    Attribute,
    Buffer,
    DataDescriptor,
    Header,
    MattrFile,
    Mesh,
    ObjectEntry,
    Topology,
    TopologyData,
)
from .mattr_utils import matrix_to_column_major_list


_COMPONENT_SIZES = {
    "F32": 4,
    "I32": 4,
    "U32": 4,
    "BOOL": 1,
}


def write_mattr(
    filepath: str,
    objects: Sequence[bpy.types.Object],
    coordinate_system_preset: str = "MATTR_DEFAULT",
    export_attributes: bool = True,
    exclude_hidden_attributes: bool = True,
    excluded_attribute_names: str = "",
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[str]:
    """Export one or more mesh objects as a MATTR file pair.

    Args:
        filepath: Destination .mattr.json path.
        objects: Sequence of Blender MESH objects to export.
        coordinate_system_preset: "BLENDER" or "MATTR_DEFAULT".
        export_attributes: Whether to export mesh attributes.
        exclude_hidden_attributes: Skip internal/hidden attributes.
        excluded_attribute_names: Comma-separated attribute names to skip.
        progress_callback: Optional callback receiving processed object count.

    Returns:
        List of warning messages collected during export.
    """
    path = Path(filepath)
    bin_path = path.parent / (path.stem + ".bin")
    bin_uri = bin_path.name

    converter = CoordinateConverter(coordinate_system_preset)
    target_cs = converter.target

    excluded_names = _parse_excluded_attribute_names(excluded_attribute_names)
    buffer = mattr_binary.BinaryBuffer()

    mesh_to_index: dict[bpy.types.Mesh, int] = {}
    meshes: list[Mesh] = []
    object_entries: list[ObjectEntry] = []
    all_warnings: list[str] = []

    for obj_index, obj in enumerate(objects):
        mesh = obj.data
        if mesh not in mesh_to_index:
            topology_data = mattr_mesh.extract_topology(mesh, converter)
            attribute_arrays, warnings = mattr_attribute.extract_attributes(
                mesh,
                topology_data.element_counts,
                export_attributes=export_attributes,
                exclude_hidden=exclude_hidden_attributes,
                excluded_names=excluded_names,
            )
            all_warnings.extend(warnings)

            mattr_mesh_obj = _append_mesh(buffer, mesh.name, topology_data, attribute_arrays)
            index = len(meshes)
            mesh_to_index[mesh] = index
            meshes.append(mattr_mesh_obj)
        else:
            index = mesh_to_index[mesh]

        object_entries.append(
            ObjectEntry(
                name=obj.name,
                type="MESH",
                index=index,
                transform=matrix_to_column_major_list(
                    converter.convert_matrix(obj.matrix_world)
                ),
            )
        )

        if progress_callback is not None:
            progress_callback(obj_index + 1)

    mattr_file = MattrFile(
        header=Header(),
        buffer=Buffer(uri=bin_uri, byte_length=buffer.byte_length()),
        coordinate_system=target_cs,
        objects=object_entries,
        meshes=meshes,
    )

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mattr_file.to_dict(), f, indent=4, ensure_ascii=False)
        buffer.write(bin_path)
    except Exception:
        # Remove incomplete file pair if writing fails mid-way.
        path.unlink(missing_ok=True)
        bin_path.unlink(missing_ok=True)
        raise

    return all_warnings


def _parse_excluded_attribute_names(names_str: str) -> set[str]:
    """Parse a comma-separated attribute name string into a set."""
    return {name.strip() for name in names_str.split(",") if name.strip()}


def _append_mesh(
    buffer: mattr_binary.BinaryBuffer,
    mesh_name: str,
    topology_data: TopologyData,
    attribute_arrays: Sequence[mattr_attribute.AttributeArrays],
) -> Mesh:
    """Append topology and attributes for a single mesh to the binary buffer."""
    counts = topology_data.element_counts

    positions_offset = buffer.append_f32(topology_data.positions)
    edges_offset = buffer.append_u32(topology_data.edges)
    corner_vertices_offset = buffer.append_u32(topology_data.corner_vertices)
    corner_edges_offset = buffer.append_u32(topology_data.corner_edges)
    face_offsets_offset = buffer.append_u32(topology_data.face_offsets)

    attributes = _append_attributes(buffer, attribute_arrays)

    topology = Topology(
        positions=DataDescriptor(
            byte_offset=positions_offset,
            byte_length=len(topology_data.positions) * 4,
            component_type="F32",
            component_count=3,
            element_count=counts.vertices,
        ),
        edges=DataDescriptor(
            byte_offset=edges_offset,
            byte_length=len(topology_data.edges) * 4,
            component_type="U32",
            component_count=2,
            element_count=counts.edges,
        ),
        corner_vertices=DataDescriptor(
            byte_offset=corner_vertices_offset,
            byte_length=len(topology_data.corner_vertices) * 4,
            component_type="U32",
            component_count=1,
            element_count=counts.corners,
        ),
        corner_edges=DataDescriptor(
            byte_offset=corner_edges_offset,
            byte_length=len(topology_data.corner_edges) * 4,
            component_type="U32",
            component_count=1,
            element_count=counts.corners,
        ),
        face_offsets=DataDescriptor(
            byte_offset=face_offsets_offset,
            byte_length=len(topology_data.face_offsets) * 4,
            component_type="U32",
            component_count=1,
            element_count=counts.faces + 1,
        ),
    )

    return Mesh(
        name=mesh_name,
        element_counts=counts,
        topology=topology,
        attributes=attributes,
    )


def _append_attributes(
    buffer: mattr_binary.BinaryBuffer, attribute_arrays: Sequence[mattr_attribute.AttributeArrays]
) -> list[Attribute]:
    """Append attribute arrays to the binary buffer and build descriptors."""
    attributes: list[Attribute] = []
    for attr in attribute_arrays:
        if attr.component_type == "F32":
            offset = buffer.append_f32(attr.values)
        elif attr.component_type == "I32":
            offset = buffer.append_i32(attr.values)
        elif attr.component_type == "U32":
            offset = buffer.append_u32(attr.values)
        elif attr.component_type == "BOOL":
            offset = buffer.append_bool(attr.values)
        else:
            raise ValueError(f"Unsupported attribute component type: {attr.component_type}")

        component_size = _COMPONENT_SIZES[attr.component_type]
        attributes.append(
            Attribute(
                name=attr.name,
                domain=attr.domain,
                data=DataDescriptor(
                    byte_offset=offset,
                    byte_length=len(attr.values) * component_size,
                    component_type=attr.component_type,
                    component_count=attr.component_count,
                    element_count=len(attr.values) // attr.component_count,
                ),
            )
        )
    return attributes
