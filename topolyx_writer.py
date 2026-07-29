"""Assemble and write Topolyx JSON + binary files as a single `.tlyx` container."""

import json
from pathlib import Path
from typing import Callable, List, Optional, Sequence

import bpy
from mathutils import Quaternion, Vector

from . import topolyx_attribute, topolyx_binary, topolyx_coordinate, topolyx_mesh
from .topolyx_binary import write_tlyx_container
from .topolyx_coordinate import CoordinateConverter
from .topolyx_types import (
    Attribute,
    CoordinateSystem,
    DataDescriptor,
    Header,
    TopolyxFile,
    Mesh,
    ObjectEntry,
    Topology,
    TopologyData,
)
from .topolyx_utils import matrix_to_column_major_list


_COMPONENT_SIZES = {
    "F32": 4,
    "I32": 4,
    "U32": 4,
    "I8": 1,
    "U8": 1,
    "BOOL": 1,
}


def write_topolyx(
    filepath: str,
    objects: Sequence[bpy.types.Object],
    coordinate_system: CoordinateSystem,
    export_attributes: bool = True,
    exclude_hidden_attributes: bool = True,
    excluded_attribute_names: str = "",
    remove_semantic_prefix: bool = False,
    auto_assign_semantics: bool = True,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[str]:
    """Export one or more mesh objects as a Topolyx file.

    Args:
        filepath: Destination .tlyx path.
        objects: Sequence of Blender MESH objects to export.
        coordinate_system: Target CoordinateSystem descriptor.
        export_attributes: Whether to export mesh attributes.
        exclude_hidden_attributes: Skip internal/hidden attributes.
        excluded_attribute_names: Comma-separated attribute names to skip.
        remove_semantic_prefix: Strip semantic prefix (e.g. DIRECTION_) from attribute names.
        auto_assign_semantics: Detect and assign semantic for standard attribute names.
        progress_callback: Optional callback receiving processed object count.

    Returns:
        List of warning messages collected during export.
    """
    path = _ensure_tlyx_ext(Path(filepath))

    converter = CoordinateConverter(coordinate_system)
    target_cs = converter.target

    excluded_names = _parse_excluded_attribute_names(excluded_attribute_names)
    buffer = topolyx_binary.BinaryBuffer()

    mesh_to_index: dict[bpy.types.Mesh, int] = {}
    meshes: list[Mesh] = []
    object_entries: list[ObjectEntry] = []
    all_warnings: list[str] = []

    for obj_index, obj in enumerate(objects):
        mesh = obj.data
        if mesh not in mesh_to_index:
            topology_data = topolyx_mesh.extract_topology(mesh, converter)
            attribute_arrays, warnings = topolyx_attribute.extract_attributes(
                mesh,
                topology_data.element_counts,
                export_attributes=export_attributes,
                exclude_hidden=exclude_hidden_attributes,
                excluded_names=excluded_names,
                remove_semantic_prefix=remove_semantic_prefix,
                auto_assign_semantics=auto_assign_semantics,
            )
            all_warnings.extend(warnings)

            topolyx_mesh_obj = _append_mesh(
                buffer, mesh.name, topology_data, attribute_arrays, converter
            )
            index = len(meshes)
            mesh_to_index[mesh] = index
            meshes.append(topolyx_mesh_obj)
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

    topolyx_file = TopolyxFile(
        header=Header(),
        coordinate_system=target_cs,
        objects=object_entries,
        meshes=meshes,
    )

    try:
        json_bytes = json.dumps(
            topolyx_file.to_dict(), indent=4, ensure_ascii=False
        ).encode("utf-8")
        container_bytes = write_tlyx_container(json_bytes, buffer.to_bytes())
        path.write_bytes(container_bytes)
    except Exception:
        # 쓰기 도중 실패하면 불완전한 파일을 제거한다.
        path.unlink(missing_ok=True)
        raise

    return all_warnings


def _parse_excluded_attribute_names(names_str: str) -> set[str]:
    """Parse a comma-separated attribute name string into a set."""
    return {name.strip() for name in names_str.split(",") if name.strip()}


def _ensure_tlyx_ext(path: Path) -> Path:
    """filepath가 .tlyx로 끝나도록 보정한다."""
    name = str(path)
    if name.endswith(".tlyx"):
        return path
    if name.endswith(".tlyx.json"):
        return Path(name[:-10] + ".tlyx")
    if name.endswith(".json"):
        return Path(name[:-5] + ".tlyx")
    return path.with_suffix(".tlyx")


def _append_mesh(
    buffer: topolyx_binary.BinaryBuffer,
    mesh_name: str,
    topology_data: TopologyData,
    attribute_arrays: Sequence[topolyx_attribute.AttributeArrays],
    converter: CoordinateConverter,
) -> Mesh:
    """Append topology and attributes for a single mesh to the binary buffer."""
    counts = topology_data.element_counts

    positions_offset = buffer.append_f32(topology_data.positions)
    edges_offset = buffer.append_u32(topology_data.edges)
    corner_vertices_offset = buffer.append_u32(topology_data.corner_vertices)
    corner_edges_offset = buffer.append_u32(topology_data.corner_edges)
    face_offsets_offset = buffer.append_u32(topology_data.face_offsets)

    attributes = _append_attributes(buffer, attribute_arrays, converter)

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
    buffer: topolyx_binary.BinaryBuffer,
    attribute_arrays: Sequence[topolyx_attribute.AttributeArrays],
    converter: CoordinateConverter,
) -> list[Attribute]:
    """Append attribute arrays to the binary buffer and build descriptors."""
    attributes: list[Attribute] = []
    for attr in attribute_arrays:
        values = _convert_attribute_values(
            attr.values, attr.semantic, attr.component_type, attr.component_count, converter
        )

        if attr.component_type == "F32":
            offset = buffer.append_f32(values)
        elif attr.component_type == "I32":
            offset = buffer.append_i32(values)
        elif attr.component_type == "U32":
            offset = buffer.append_u32(values)
        elif attr.component_type == "I8":
            offset = buffer.append_i8(values)
        elif attr.component_type == "U8":
            offset = buffer.append_u8(values)
        elif attr.component_type == "BOOL":
            offset = buffer.append_bool(values)
        else:
            raise ValueError(f"Unsupported attribute component type: {attr.component_type}")

        component_size = _COMPONENT_SIZES[attr.component_type]
        attributes.append(
            Attribute(
                name=attr.name,
                domain=attr.domain,
                semantic=attr.semantic,
                data=DataDescriptor(
                    byte_offset=offset,
                    byte_length=len(values) * component_size,
                    component_type=attr.component_type,
                    component_count=attr.component_count,
                    element_count=len(values) // attr.component_count,
                ),
            )
        )
    return attributes


def _convert_attribute_values(
    values: List[float] | List[int],
    semantic: str,
    component_type: str,
    component_count: int,
    converter: CoordinateConverter,
) -> List[float] | List[int]:
    """좌표계 변환이 필요한 semantic attribute 값을 변환한다."""
    if component_type != "F32":
        return values

    if semantic == "POSITION":
        return _convert_vectors(values, converter.convert_position)
    elif semantic == "DIRECTION":
        return _convert_vectors(values, converter.convert_direction)
    elif semantic == "NORMAL":
        return _convert_vectors(values, converter.convert_normal)
    elif semantic == "ROTATION":
        return _convert_quaternions(values, converter.convert_rotation)
    elif semantic == "TANGENT":
        return _convert_tangents(values, converter.convert_tangent)
    return values


def _convert_vectors(
    values: Sequence[float], convert_fn: Callable[[Vector], Vector]
) -> List[float]:
    """F32×3 벡터 배열에 변환 함수를 적용한다."""
    result: List[float] = []
    for i in range(0, len(values), 3):
        v = convert_fn(Vector((values[i], values[i + 1], values[i + 2])))
        result.extend((v.x, v.y, v.z))
    return result


def _convert_quaternions(
    values: Sequence[float], convert_fn: Callable[[Quaternion], Quaternion]
) -> List[float]:
    """F32×4 쿼터니언 배열 (x, y, z, w)에 변환 함수를 적용한다."""
    result: List[float] = []
    for i in range(0, len(values), 4):
        q = Quaternion((values[i + 3], values[i], values[i + 1], values[i + 2]))
        q = convert_fn(q)
        result.extend((q.x, q.y, q.z, q.w))
    return result


def _convert_tangents(
    values: Sequence[float], convert_fn: Callable[[Vector], Vector]
) -> List[float]:
    """F32×4 tangent 배열 (x, y, z, w)에 변환 함수를 적용한다."""
    result: List[float] = []
    for i in range(0, len(values), 4):
        t = convert_fn(Vector((values[i], values[i + 1], values[i + 2], values[i + 3])))
        result.extend((t.x, t.y, t.z, t.w))
    return result
