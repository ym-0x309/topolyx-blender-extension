"""Blender Mesh 데이터 블록에서 MATTR 토폴로지 데이터를 추출한다."""

from typing import List

import bpy

from .mattr_coordinate import CoordinateConverter
from .mattr_types import ElementCounts, TopologyData


def extract_topology(
    mesh: bpy.types.Mesh, converter: CoordinateConverter
) -> TopologyData:
    """Blender Mesh로부터 MATTR 필수 토폴로지 배열을 추출한다.

    positions, edges, corner_vertices, corner_edges, face_offsets를
    flat list 형태로 반환한다. ``converter``를 통해 positions는
    target coordinate system으로 변환된다.
    """
    positions = _extract_positions(mesh, converter)
    edges = _extract_edges(mesh)
    corner_vertices = _extract_corner_vertices(mesh)
    corner_edges = _extract_corner_edges(mesh)
    face_offsets = _extract_face_offsets(mesh)

    element_counts = ElementCounts(
        vertices=len(mesh.vertices),
        edges=len(mesh.edges),
        faces=len(mesh.polygons),
        corners=len(mesh.loops),
    )

    return TopologyData(
        positions=positions,
        edges=edges,
        corner_vertices=corner_vertices,
        corner_edges=corner_edges,
        face_offsets=face_offsets,
        element_counts=element_counts,
    )


def _extract_positions(
    mesh: bpy.types.Mesh, converter: CoordinateConverter
) -> List[float]:
    """각 vertex의 local space 위치를 target 좌표계로 변환하여 flat F32 배열로 반환한다."""
    positions: List[float] = []
    for vertex in mesh.vertices:
        co = converter.convert_position(vertex.co)
        positions.extend((co.x, co.y, co.z))
    return positions


def _extract_edges(mesh: bpy.types.Mesh) -> List[int]:
    """각 edge를 구성하는 두 vertex index를 flat U32 배열로 반환한다."""
    edges: List[int] = []
    for edge in mesh.edges:
        v0, v1 = edge.vertices
        edges.extend((v0, v1))
    return edges


def _extract_corner_vertices(mesh: bpy.types.Mesh) -> List[int]:
    """각 corner가 참조하는 vertex index를 flat U32 배열로 반환한다."""
    return [loop.vertex_index for loop in mesh.loops]


def _extract_corner_edges(mesh: bpy.types.Mesh) -> List[int]:
    """각 corner에서 다음 corner로 이어지는 edge index를 flat U32 배열로 반환한다."""
    return [loop.edge_index for loop in mesh.loops]


def _extract_face_offsets(mesh: bpy.types.Mesh) -> List[int]:
    """각 face의 corner 범위 시작 index를 flat U32 배열로 반환한다.

    길이는 faces + 1이며, 마지막 값은 전체 corner 수와 같다.
    face_offsets[i]는 mesh.polygons[i]에 대응해야 한다.
    """
    face_offsets = [poly.loop_start for poly in mesh.polygons]
    face_offsets.append(len(mesh.loops))
    return face_offsets
