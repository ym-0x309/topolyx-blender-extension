"""MATTR JSON + binary 파일을 조립하여 쓴다."""

import json
from pathlib import Path
from typing import List

import bpy

from . import mattr_binary, mattr_coordinate, mattr_mesh
from .mattr_coordinate import CoordinateConverter
from .mattr_types import (
    Buffer,
    DataDescriptor,
    Header,
    MattrFile,
    Mesh,
    ObjectEntry,
    Topology,
)


def write_mattr(
    filepath: str, obj: bpy.types.Object, coordinate_system_preset: str = "MATTR_DEFAULT"
) -> None:
    """단일 메시 오브젝트를 MATTR 파일 쌍으로 낸 장한다.

    - filepath: 사용자가 선택한 .mattr.json 경로
    - obj: 낸 장할 MESH 타입 Blender 오브젝트
    - coordinate_system_preset: "BLENDER" 또는 "MATTR_DEFAULT"
    """
    path = Path(filepath)
    bin_path = path.parent / (path.stem + ".bin")
    bin_uri = bin_path.name

    converter = CoordinateConverter(coordinate_system_preset)
    target_cs = converter.target

    mesh = obj.data
    topology_data = mattr_mesh.extract_topology(mesh, converter)

    buffer = mattr_binary.BinaryBuffer()
    positions_offset = buffer.append_f32(topology_data.positions)
    edges_offset = buffer.append_u32(topology_data.edges)
    corner_vertices_offset = buffer.append_u32(topology_data.corner_vertices)
    corner_edges_offset = buffer.append_u32(topology_data.corner_edges)
    face_offsets_offset = buffer.append_u32(topology_data.face_offsets)

    counts = topology_data.element_counts
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

    mattr_file = MattrFile(
        header=Header(),
        buffer=Buffer(uri=bin_uri, byte_length=buffer.byte_length()),
        coordinate_system=target_cs,
        objects=[
            ObjectEntry(
                name=obj.name,
                type="MESH",
                index=0,
                transform=_matrix_to_column_major_list(
                    converter.convert_matrix(obj.matrix_world)
                ),
            )
        ],
        meshes=[
            Mesh(
                name=mesh.name,
                element_counts=counts,
                topology=topology,
            )
        ],
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(mattr_file.to_dict(), f, indent=4, ensure_ascii=False)

    buffer.write(bin_path)


def _matrix_to_column_major_list(matrix) -> List[float]:
    """Blender mathutils.Matrix를 column-major 16개 float list로 변환한다.

    Blender Python API에서는 matrix[row][col]이 row-major 접근 표기를 사용하므로,
    column-major 직렬화를 위해 col을 바깥 루프로 순회한다.
    """
    return [matrix[row][col] for col in range(4) for row in range(4)]
