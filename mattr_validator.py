"""MATTR 출력 파일의 유효성을 검증한다."""

import struct
from typing import Any, Dict, Optional


_COMPONENT_SIZES = {
    "F32": 4,
    "I32": 4,
    "U32": 4,
}


def validate_mattr(json_data: Dict[str, Any], bin_data: bytes) -> None:
    """JSON 메타데이터와 binary 데이터가 명세 조건을 만족하는지 검증한다."""
    _validate_header(json_data)
    _validate_buffer(json_data, bin_data)
    _validate_coordinate_system(json_data)

    for mesh in json_data["meshes"]:
        _validate_mesh(mesh, bin_data)

    for obj in json_data["objects"]:
        _validate_object(obj, len(json_data["meshes"]))


def _validate_header(json_data: Dict[str, Any]) -> None:
    header = json_data["header"]
    assert header["format"] == "MATTR", f"Unexpected format: {header['format']}"
    assert header["version"] == "0.1.0", f"Unexpected version: {header['version']}"


def _validate_buffer(json_data: Dict[str, Any], bin_data: bytes) -> None:
    buffer = json_data["buffer"]
    assert buffer["byte_length"] == len(bin_data), (
        f"Buffer byte_length mismatch: {buffer['byte_length']} vs {len(bin_data)}"
    )


def _validate_coordinate_system(json_data: Dict[str, Any]) -> None:
    cs = json_data["coordinate_system"]
    assert cs["handedness"] in ("RIGHT", "LEFT")
    assert cs["winding"] in ("CW", "CCW")

    valid_axes = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
    up = cs["up_axis"]
    forward = cs["forward_axis"]
    assert up in valid_axes, f"Invalid up_axis: {up}"
    assert forward in valid_axes, f"Invalid forward_axis: {forward}"
    assert up[1] != forward[1], (
        f"up_axis and forward_axis must not be parallel: {up}, {forward}"
    )


def _validate_mesh(mesh: Dict[str, Any], bin_data: bytes) -> None:
    counts = mesh["element_counts"]
    topo = mesh["topology"]

    _validate_descriptor(
        topo["positions"], bin_data, expected_component="F32", expected_count=3, expected_elements=counts["vertices"]
    )
    _validate_descriptor(
        topo["edges"], bin_data, expected_component="U32", expected_count=2, expected_elements=counts["edges"]
    )
    _validate_descriptor(
        topo["corner_vertices"], bin_data, expected_component="U32", expected_count=1, expected_elements=counts["corners"]
    )
    _validate_descriptor(
        topo["corner_edges"], bin_data, expected_component="U32", expected_count=1, expected_elements=counts["corners"]
    )
    _validate_descriptor(
        topo["face_offsets"], bin_data, expected_component="U32", expected_count=1, expected_elements=counts["faces"] + 1
    )

    _validate_face_offsets(topo["face_offsets"], counts, bin_data)
    _validate_index_ranges(topo, counts, bin_data)
    _validate_corner_edge_consistency(topo, counts, bin_data)
    _validate_attributes(mesh, bin_data)


_DOMAIN_COUNT_KEY = {
    "POINT": "vertices",
    "EDGE": "edges",
    "FACE": "faces",
    "CORNER": "corners",
}


def _validate_descriptor(
    desc: Dict[str, Any],
    bin_data: bytes,
    expected_component: Optional[str],
    expected_count: Optional[int],
    expected_elements: int,
) -> None:
    assert desc["byte_offset"] % 4 == 0, f"Misaligned byte_offset: {desc['byte_offset']}"
    assert desc["component_type"] in _COMPONENT_SIZES, (
        f"Invalid component_type: {desc['component_type']}"
    )
    if expected_component is not None:
        assert desc["component_type"] == expected_component
    if expected_count is not None:
        assert desc["component_count"] == expected_count
    assert desc["element_count"] == expected_elements

    component_size = _COMPONENT_SIZES[desc["component_type"]]
    expected_length = component_size * desc["component_count"] * desc["element_count"]
    assert desc["byte_length"] == expected_length, (
        f"byte_length mismatch: {desc['byte_length']} vs {expected_length}"
    )
    assert desc["byte_offset"] + desc["byte_length"] <= len(bin_data), (
        f"Descriptor overflows buffer: {desc['byte_offset']} + {desc['byte_length']}"
    )


def _validate_face_offsets(face_offsets_desc: Dict[str, Any], counts: Dict[str, int], bin_data: bytes) -> None:
    values = _unpack_u32(face_offsets_desc, bin_data)

    assert values[0] == 0, f"face_offsets[0] must be 0, got {values[0]}"
    assert values[-1] == counts["corners"], (
        f"face_offsets[-1] must equal corners, got {values[-1]} vs {counts['corners']}"
    )

    for i in range(len(values) - 1):
        assert values[i] <= values[i + 1], f"face_offsets must be non-decreasing: {values}"
        # 빈 메시(faces=0)에서는 이 루프가 실행되지 않음
        if counts["faces"] > 0:
            assert values[i + 1] - values[i] >= 3, (
                f"Each face must have at least 3 corners: {values[i]} -> {values[i + 1]}"
            )


def _validate_index_ranges(topo: Dict[str, Any], counts: Dict[str, int], bin_data: bytes) -> None:
    vertices_count = counts["vertices"]
    edges_count = counts["edges"]

    edges = _unpack_u32(topo["edges"], bin_data)
    for idx in edges:
        assert 0 <= idx < vertices_count, f"Edge vertex index out of range: {idx}"

    corner_vertices = _unpack_u32(topo["corner_vertices"], bin_data)
    for idx in corner_vertices:
        assert 0 <= idx < vertices_count, f"Corner vertex index out of range: {idx}"

    corner_edges = _unpack_u32(topo["corner_edges"], bin_data)
    for idx in corner_edges:
        assert 0 <= idx < edges_count, f"Corner edge index out of range: {idx}"


def _validate_corner_edge_consistency(topo: Dict[str, Any], counts: Dict[str, int], bin_data: bytes) -> None:
    """corner_edges[c]가 corner_vertices[c]와 corner_vertices[next]를 연결하는지 검증한다."""
    face_offsets = _unpack_u32(topo["face_offsets"], bin_data)
    corner_vertices = _unpack_u32(topo["corner_vertices"], bin_data)
    corner_edges = _unpack_u32(topo["corner_edges"], bin_data)
    edges = _unpack_u32(topo["edges"], bin_data)

    # edge별 vertex 집합 (순서 무관)
    edge_vertices = []
    for i in range(0, len(edges), 2):
        edge_vertices.append({edges[i], edges[i + 1]})

    for face_index in range(counts["faces"]):
        start = face_offsets[face_index]
        end = face_offsets[face_index + 1]
        for c in range(start, end):
            n = c + 1 if c + 1 < end else start
            edge_idx = corner_edges[c]
            expected = {corner_vertices[c], corner_vertices[n]}
            actual = edge_vertices[edge_idx]
            assert actual == expected, (
                f"Corner-edge inconsistency at corner {c}: edge {edge_idx} has {actual}, expected {expected}"
            )


def _validate_attributes(mesh: Dict[str, Any], bin_data: bytes) -> None:
    """일반 attribute의 descriptor와 domain/element_count 일관성을 검증한다."""
    counts = mesh["element_counts"]
    attributes = mesh.get("attributes", [])
    seen_names = set()

    for attr in attributes:
        name = attr["name"]
        assert name, "Attribute name must not be empty"
        assert name not in seen_names, f"Duplicate attribute name: {name}"
        seen_names.add(name)

        domain = attr["domain"]
        assert domain in _DOMAIN_COUNT_KEY, f"Invalid attribute domain: {domain}"

        expected_elements = counts[_DOMAIN_COUNT_KEY[domain]]
        _validate_descriptor(
            attr["data"],
            bin_data,
            expected_component=None,
            expected_count=None,
            expected_elements=expected_elements,
        )
        assert attr["data"]["component_count"] >= 1, (
            f"component_count must be >= 1 for attribute '{name}'"
        )


def _validate_object(obj: Dict[str, Any], mesh_count: int) -> None:
    assert obj["type"] == "MESH"
    assert 0 <= obj["index"] < mesh_count
    assert len(obj["transform"]) == 16


def _unpack_u32(desc: Dict[str, Any], bin_data: bytes) -> list:
    offset = desc["byte_offset"]
    count = desc["element_count"] * desc["component_count"]
    return list(struct.unpack_from(f"<{count}I", bin_data, offset))
