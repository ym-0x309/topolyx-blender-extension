"""MATTR topology 배열로 Blender Mesh 데이터 블록을 복원한다."""

from typing import List, Sequence

import bpy


def build_blender_mesh(
    name: str,
    positions: Sequence[float],
    edges: Sequence[int],
    corner_vertices: Sequence[int],
    corner_edges: Sequence[int],
    face_offsets: Sequence[int],
    winding: str = "CCW",
) -> bpy.types.Mesh:
    """MATTR topology 배열로 Blender Mesh 데이터 블록을 생성한다.

    Args:
        name: 생성할 mesh 데이터 블록 이름.
        positions: Blender 좌표계 기준 flat F32 배열. 길이는 vertices * 3.
        edges: flat U32 배열. 길이는 edges * 2.
        corner_vertices: flat U32 배열. 길이는 corners.
        corner_edges: flat U32 배열. 길이는 corners.
        face_offsets: flat U32 배열. 길이는 faces + 1.
        winding: 파일의 winding ("CW" 또는 "CCW"). Blender는 CCW를 기본으로 하므로
            "CW"일 경우 각 face의 corner 순서를 뒤집는다.

    Returns:
        생성된 bpy.types.Mesh 데이터 블록.

    Raises:
        ValueError: topology 배열의 길이가 일치하지 않거나, duplicate edge가 있을 경우.
    """
    _validate_topology_arrays(
        positions, edges, corner_vertices, corner_edges, face_offsets
    )

    faces = _build_faces(corner_vertices, face_offsets)
    reversed_corner_edges = list(corner_edges)

    if winding == "CW":
        faces, reversed_corner_edges = _reverse_face_winding(
            faces, reversed_corner_edges, face_offsets
        )
    elif winding != "CCW":
        raise ValueError(f"Unsupported winding: {winding!r} (expected 'CW' or 'CCW')")

    vertices = [
        (positions[i], positions[i + 1], positions[i + 2])
        for i in range(0, len(positions), 3)
    ]
    edge_pairs = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]

    mesh = bpy.data.meshes.new(name)
    try:
        mesh.from_pydata(vertices, edge_pairs, faces)
        mesh.update()
        _override_loop_edge_indices(mesh, reversed_corner_edges)
        mesh.validate(verbose=False)
    except Exception:
        bpy.data.meshes.remove(mesh)
        raise

    return mesh


def _validate_topology_arrays(
    positions: Sequence[float],
    edges: Sequence[int],
    corner_vertices: Sequence[int],
    corner_edges: Sequence[int],
    face_offsets: Sequence[int],
) -> None:
    """입력 topology 배열의 기본적인 일관성을 검사한다."""
    if len(positions) % 3 != 0:
        raise ValueError(
            f"positions length must be a multiple of 3, got {len(positions)}"
        )

    if len(edges) % 2 != 0:
        raise ValueError(f"edges length must be a multiple of 2, got {len(edges)}")

    if len(corner_vertices) != len(corner_edges):
        raise ValueError(
            f"corner_vertices length ({len(corner_vertices)}) must match "
            f"corner_edges length ({len(corner_edges)})"
        )

    if len(face_offsets) < 1:
        raise ValueError("face_offsets must contain at least one value")

    if face_offsets[0] != 0:
        raise ValueError(f"face_offsets[0] must be 0, got {face_offsets[0]}")

    if face_offsets[-1] != len(corner_vertices):
        raise ValueError(
            f"face_offsets[-1] must equal corners count "
            f"({len(corner_vertices)}), got {face_offsets[-1]}"
        )

    seen_edges = set()
    for i in range(0, len(edges), 2):
        v0, v1 = edges[i], edges[i + 1]
        if v0 == v1:
            raise ValueError(f"Self-edge detected: ({v0}, {v1})")
        key = (min(v0, v1), max(v0, v1))
        if key in seen_edges:
            raise ValueError(f"Duplicate edge detected: ({v0}, {v1})")
        seen_edges.add(key)


def _build_faces(
    corner_vertices: Sequence[int], face_offsets: Sequence[int]
) -> List[List[int]]:
    """face_offsets를 기준으로 corner_vertices를 face별 list로 분할한다."""
    faces: List[List[int]] = []
    for i in range(len(face_offsets) - 1):
        start = face_offsets[i]
        end = face_offsets[i + 1]
        faces.append(list(corner_vertices[start:end]))
    return faces


def _reverse_face_winding(
    faces: List[List[int]],
    corner_edges: Sequence[int],
    face_offsets: Sequence[int],
) -> tuple[List[List[int]], List[int]]:
    """CW winding을 Blender의 CCW에 맞춰 각 face의 corner 순서를 뒤집는다."""
    reversed_faces: List[List[int]] = []
    reversed_corner_edges: List[int] = []

    for face, start, end in zip(
        faces, face_offsets[:-1], face_offsets[1:]
    ):
        reversed_faces.append(list(reversed(face)))
        reversed_corner_edges.extend(reversed(corner_edges[start:end]))

    return reversed_faces, reversed_corner_edges


def _override_loop_edge_indices(
    mesh: bpy.types.Mesh, corner_edges: Sequence[int]
) -> None:
    """mesh.loops의 edge_index가 corner_edges와 일치하도록 강제한다."""
    if len(mesh.loops) != len(corner_edges):
        raise ValueError(
            f"Loop count mismatch: mesh has {len(mesh.loops)} loops, "
            f"but corner_edges has {len(corner_edges)}"
        )

    for loop, expected_edge in zip(mesh.loops, corner_edges):
        if loop.edge_index != expected_edge:
            loop.edge_index = expected_edge
    mesh.update()
