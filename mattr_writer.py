"""MATTR JSON + binary 파일을 조립하여 쓴다."""

import json
from pathlib import Path
from typing import List, Sequence

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


def write_mattr(
    filepath: str,
    objects: Sequence[bpy.types.Object],
    coordinate_system_preset: str = "MATTR_DEFAULT",
    export_attributes: bool = True,
    exclude_hidden_attributes: bool = True,
    excluded_attribute_names: str = "",
) -> None:
    """하나 이상의 메시 오브젝트를 MATTR 파일 쌍으로 낸 장한다.

    - filepath: 사용자가 선택한 .mattr.json 경로
    - objects: 낸 장할 MESH 타입 Blender 오브젝트 목록
    - coordinate_system_preset: "BLENDER" 또는 "MATTR_DEFAULT"
    - export_attributes: attribute 낸 장 여부
    - exclude_hidden_attributes: '.select_*', 'position' 등 난 Outputplus/internal attribute 제외
    - excluded_attribute_names: 쉼표로 구분된 추가 제외 attribute 이름
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

    for obj in objects:
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
            for warning in warnings:
                print(f"MATTR export warning: {warning}")

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
                transform=_matrix_to_column_major_list(
                    converter.convert_matrix(obj.matrix_world)
                ),
            )
        )

    mattr_file = MattrFile(
        header=Header(),
        buffer=Buffer(uri=bin_uri, byte_length=buffer.byte_length()),
        coordinate_system=target_cs,
        objects=object_entries,
        meshes=meshes,
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(mattr_file.to_dict(), f, indent=4, ensure_ascii=False)

    buffer.write(bin_path)


def _parse_excluded_attribute_names(names_str: str) -> set[str]:
    """쉼표로 구분된 attribute 이름 문자열을 집합으로 변환한다."""
    return {name.strip() for name in names_str.split(",") if name.strip()}


def _append_mesh(
    buffer: mattr_binary.BinaryBuffer,
    mesh_name: str,
    topology_data: TopologyData,
    attribute_arrays: Sequence[mattr_attribute.AttributeArrays],
) -> Mesh:
    """하나의 메시에 대해 topology와 attributes를 binary 버퍼에 기록한다."""
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
    """attribute 배열들을 binary 버퍼에 추가하고 descriptor를 생성한다."""
    attributes: list[Attribute] = []
    for attr in attribute_arrays:
        if attr.component_type == "F32":
            offset = buffer.append_f32(attr.values)
        elif attr.component_type == "I32":
            offset = buffer.append_i32(attr.values)
        elif attr.component_type == "U32":
            offset = buffer.append_u32(attr.values)
        else:
            raise ValueError(f"Unsupported attribute component type: {attr.component_type}")

        attributes.append(
            Attribute(
                name=attr.name,
                domain=attr.domain,
                data=DataDescriptor(
                    byte_offset=offset,
                    byte_length=len(attr.values) * 4,
                    component_type=attr.component_type,
                    component_count=attr.component_count,
                    element_count=len(attr.values) // attr.component_count,
                ),
            )
        )
    return attributes


def _matrix_to_column_major_list(matrix) -> List[float]:
    """Blender mathutils.Matrix를 column-major 16개 float list로 변환한다.

    Blender Python API에서는 matrix[row][col]이 row-major 접근 표기를 사용하므로,
    column-major 직렬화를 위해 col을 바깥 루프로 순회한다.
    """
    return [matrix[row][col] for col in range(4) for row in range(4)]
