"""Topolyx 출력 파일의 유효성을 검증한다."""

import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Dict, Optional


_COMPONENT_SIZES = {
    "F32": 4,
    "I32": 4,
    "U32": 4,
    "I8": 1,
    "U8": 1,
    "BOOL": 1,
}

_VERSION_PATTERN = re.compile(r"^\d+\.\d+(?:\.\d+)?$")

# 이 익스포터/리더가 지원하는 Topolyx 포맷 버전(문서 기준 x.y.z).
_SUPPORTED_VERSION = "0.3.0"
_SUPPORTED_MAJOR_VERSION = _SUPPORTED_VERSION.split(".")[0]
_SUPPORTED_MINOR_VERSION = _SUPPORTED_VERSION.split(".")[1]

# 64-bit unsigned 최대값. byte_offset + byte_length overflow를 방지하기 위한 상한.
_MAX_BUFFER_OFFSET = 2**64 - 1


class TopolyxValidationError(Exception):
    """Topolyx 파일이 명세 조건을 만족하지 않을 때 발생하는 예외."""

    pass


def validate_topolyx_file(json_path: Path, bin_path: Optional[Path] = None) -> None:
    """JSON 파일 경로를 기준으로 Topolyx 파일 쌍을 검증한다.

    bin_path가 주어지지 않으면 json_path와 동일한 basename의 .tlyx.bin 파일을 사용한다.
    """
    json_path = Path(json_path)
    if bin_path is None:
        bin_path = json_path.with_name(json_path.stem + ".bin")
    else:
        bin_path = Path(bin_path)

    if not json_path.exists():
        raise TopolyxValidationError(f"JSON file not found: {json_path}")
    if not bin_path.exists():
        raise TopolyxValidationError(f"Binary file not found: {bin_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    bin_data = bin_path.read_bytes()

    validate_topolyx(json_data, bin_data)


def validate_topolyx(json_data: Dict[str, Any], bin_data: bytes) -> None:
    """JSON 메타데이터와 binary 데이터가 명세 조건을 만족하는지 검증한다."""
    _validate_header(json_data)
    _validate_buffer(json_data, bin_data)
    _validate_coordinate_system(json_data)
    _validate_names(json_data)

    mesh_count = len(json_data["meshes"])
    for mesh_index, mesh in enumerate(json_data["meshes"]):
        _validate_mesh(mesh, bin_data, mesh_index)

    for obj_index, obj in enumerate(json_data["objects"]):
        _validate_object(obj, mesh_count, obj_index)


def _fail(message: str) -> None:
    """TopolyxValidationError를 발생시킨다."""
    raise TopolyxValidationError(message)


def _validate_header(json_data: Dict[str, Any]) -> None:
    header = json_data.get("header")
    if header is None:
        _fail("Missing 'header' field")

    fmt = header.get("format")
    if fmt != "Topolyx":
        _fail(f"Unexpected header.format: {fmt!r} (expected 'Topolyx')")

    version = header.get("version")
    if version is None:
        _fail("Missing header.version")
    if not isinstance(version, str) or not _VERSION_PATTERN.match(version):
        _fail(f"header.version must be in x.y.z format, got: {version!r}")

    parts = version.split(".")
    major = parts[0]
    minor = parts[1] if len(parts) > 1 else "0"
    if major != _SUPPORTED_MAJOR_VERSION:
        _fail(
            f"Unsupported major version: {version!r} "
            f"(supported major version: {_SUPPORTED_MAJOR_VERSION}.x.x)"
        )
    if minor != _SUPPORTED_MINOR_VERSION:
        _fail(
            f"Unsupported minor version: {version!r} "
            f"(supported version: {_SUPPORTED_MAJOR_VERSION}.{_SUPPORTED_MINOR_VERSION}.x)"
        )


def _validate_buffer(json_data: Dict[str, Any], bin_data: bytes) -> None:
    buffer = json_data.get("buffer")
    if buffer is None:
        _fail("Missing 'buffer' field")

    byte_length = buffer.get("byte_length")
    if byte_length != len(bin_data):
        _fail(
            f"buffer.byte_length mismatch: {byte_length} vs actual binary length {len(bin_data)}"
        )

    uri = buffer.get("uri")
    if uri is None or not isinstance(uri, str) or not uri:
        _fail("buffer.uri must be a non-empty string")


def _validate_coordinate_system(json_data: Dict[str, Any]) -> None:
    cs = json_data.get("coordinate_system")
    if cs is None:
        _fail("Missing 'coordinate_system' field")

    handedness = cs.get("handedness")
    if handedness not in ("RIGHT", "LEFT"):
        _fail(f"coordinate_system.handedness must be 'RIGHT' or 'LEFT', got: {handedness!r}")

    winding = cs.get("winding")
    if winding not in ("CW", "CCW"):
        _fail(f"coordinate_system.winding must be 'CW' or 'CCW', got: {winding!r}")

    valid_axes = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
    up = cs.get("up_axis")
    forward = cs.get("forward_axis")
    if up not in valid_axes:
        _fail(f"Invalid coordinate_system.up_axis: {up!r}")
    if forward not in valid_axes:
        _fail(f"Invalid coordinate_system.forward_axis: {forward!r}")
    if up[1] == forward[1]:
        _fail(f"up_axis and forward_axis must not be parallel: {up}, {forward}")

    meters_per_unit = cs.get("meters_per_unit")
    if not isinstance(meters_per_unit, (int, float)):
        _fail(
            f"coordinate_system.meters_per_unit must be a number, got: {meters_per_unit!r}"
        )
    if not math.isfinite(meters_per_unit) or meters_per_unit <= 0:
        _fail(
            f"coordinate_system.meters_per_unit must be a positive finite number, "
            f"got: {meters_per_unit!r}"
        )


def _validate_names(json_data: Dict[str, Any]) -> None:
    """object/mesh/attribute 이름이 비어 있거나 잘못 중복되지 않는지 검증한다."""
    object_names = set()
    for obj_index, obj in enumerate(json_data.get("objects", [])):
        name = obj.get("name")
        if not name or not isinstance(name, str):
            _fail(f"objects[{obj_index}].name must be a non-empty string")
        if name in object_names:
            _fail(f"objects[{obj_index}]: duplicate object name '{name}'")
        object_names.add(name)

    mesh_names = set()
    for mesh_index, mesh in enumerate(json_data.get("meshes", [])):
        name = mesh.get("name")
        if not name or not isinstance(name, str):
            _fail(f"meshes[{mesh_index}].name must be a non-empty string")
        if name in mesh_names:
            _fail(f"meshes[{mesh_index}]: duplicate mesh name '{name}'")
        mesh_names.add(name)

        attr_names = set()
        for attr_index, attr in enumerate(mesh.get("attributes", [])):
            name = attr.get("name")
            if not name or not isinstance(name, str):
                _fail(
                    f"meshes[{mesh_index}].attributes[{attr_index}].name "
                    f"must be a non-empty string"
                )
            if name in attr_names:
                _fail(
                    f"meshes[{mesh_index}].attributes[{attr_index}]: "
                    f"duplicate attribute name '{name}'"
                )
            attr_names.add(name)


def _validate_mesh(mesh: Dict[str, Any], bin_data: bytes, mesh_index: int) -> None:
    prefix = f"meshes[{mesh_index}]"

    counts = mesh.get("element_counts")
    if counts is None:
        _fail(f"{prefix}: missing 'element_counts'")

    required_counts = ("vertices", "edges", "faces", "corners")
    for key in required_counts:
        if key not in counts:
            _fail(f"{prefix}: missing element_counts.{key}")
        if not isinstance(counts[key], int) or counts[key] < 0:
            _fail(f"{prefix}: element_counts.{key} must be a non-negative integer")

    topo = mesh.get("topology")
    if topo is None:
        _fail(f"{prefix}: missing 'topology'")

    _validate_descriptor(
        topo["positions"],
        bin_data,
        prefix=f"{prefix}.topology.positions",
        expected_component="F32",
        expected_count=3,
        expected_elements=counts["vertices"],
    )
    _validate_descriptor(
        topo["edges"],
        bin_data,
        prefix=f"{prefix}.topology.edges",
        expected_component="U32",
        expected_count=2,
        expected_elements=counts["edges"],
    )
    _validate_descriptor(
        topo["corner_vertices"],
        bin_data,
        prefix=f"{prefix}.topology.corner_vertices",
        expected_component="U32",
        expected_count=1,
        expected_elements=counts["corners"],
    )
    _validate_descriptor(
        topo["corner_edges"],
        bin_data,
        prefix=f"{prefix}.topology.corner_edges",
        expected_component="U32",
        expected_count=1,
        expected_elements=counts["corners"],
    )
    _validate_descriptor(
        topo["face_offsets"],
        bin_data,
        prefix=f"{prefix}.topology.face_offsets",
        expected_component="U32",
        expected_count=1,
        expected_elements=counts["faces"] + 1,
    )

    _validate_face_offsets(topo["face_offsets"], counts, bin_data, prefix)
    _validate_index_ranges(topo, counts, bin_data, prefix)
    _validate_corner_edge_consistency(topo, counts, bin_data, prefix)
    _validate_edges(topo, counts, bin_data, prefix)
    _validate_attributes(mesh, bin_data, prefix)


_DOMAIN_COUNT_KEY = {
    "POINT": "vertices",
    "EDGE": "edges",
    "FACE": "faces",
    "CORNER": "corners",
}

_VALID_SEMANTICS = {"POSITION", "DIRECTION", "ROTATION", "TANGENT", "COLOR", "NONE"}

_SEMANTIC_CONSTRAINTS = {
    "POSITION": ("F32", 3),
    "DIRECTION": ("F32", 3),
    "ROTATION": ("F32", 4),
    "TANGENT": ("F32", 4),
    "COLOR": {("F32", 4), ("U8", 4)},
}


def _validate_descriptor(
    desc: Dict[str, Any],
    bin_data: bytes,
    prefix: str,
    expected_component: Optional[str],
    expected_count: Optional[int],
    expected_elements: int,
) -> None:
    byte_offset = desc.get("byte_offset")
    byte_length = desc.get("byte_length")
    component_type = desc.get("component_type")
    component_count = desc.get("component_count")
    element_count = desc.get("element_count")

    if not isinstance(byte_offset, int) or byte_offset < 0:
        _fail(f"{prefix}: byte_offset must be a non-negative integer, got: {byte_offset!r}")

    if not isinstance(byte_length, int) or byte_length < 0:
        _fail(f"{prefix}: byte_length must be a non-negative integer, got: {byte_length!r}")

    if byte_offset % 4 != 0:
        _fail(f"{prefix}: misaligned byte_offset: {byte_offset}")

    if component_type not in _COMPONENT_SIZES:
        _fail(f"{prefix}: invalid component_type: {component_type!r}")

    if expected_component is not None and component_type != expected_component:
        _fail(f"{prefix}: component_type must be {expected_component}, got {component_type}")

    if not isinstance(component_count, int) or component_count < 1:
        _fail(f"{prefix}: component_count must be >= 1, got {component_count}")

    if expected_count is not None and component_count != expected_count:
        _fail(f"{prefix}: component_count must be {expected_count}, got {component_count}")

    if element_count != expected_elements:
        _fail(
            f"{prefix}: element_count mismatch: {element_count} (expected {expected_elements})"
        )

    component_size = _COMPONENT_SIZES[component_type]
    expected_length = component_size * component_count * element_count
    if byte_length != expected_length:
        _fail(f"{prefix}: byte_length mismatch: {byte_length} vs {expected_length}")

    end_offset = byte_offset + byte_length
    if end_offset > len(bin_data):
        _fail(
            f"{prefix}: descriptor overflows buffer: {byte_offset} + {byte_length} > {len(bin_data)}"
        )

    if end_offset > _MAX_BUFFER_OFFSET:
        _fail(f"{prefix}: byte_offset + byte_length overflows 64-bit range")


def _validate_face_offsets(
    face_offsets_desc: Dict[str, Any],
    counts: Dict[str, int],
    bin_data: bytes,
    prefix: str,
) -> None:
    values = _unpack_u32(face_offsets_desc, bin_data)

    if values[0] != 0:
        _fail(f"{prefix}.topology.face_offsets: first value must be 0, got {values[0]}")

    if values[-1] != counts["corners"]:
        _fail(
            f"{prefix}.topology.face_offsets: last value must equal corners "
            f"({counts['corners']}), got {values[-1]}"
        )

    for i in range(len(values) - 1):
        if values[i] > values[i + 1]:
            _fail(
                f"{prefix}.topology.face_offsets: must be non-decreasing, "
                f"got {values[i]} > {values[i + 1]}"
            )
        if counts["faces"] > 0 and values[i + 1] - values[i] < 3:
            _fail(
                f"{prefix}.topology.face_offsets: each face must have at least 3 corners, "
                f"got range [{values[i]}, {values[i + 1]})"
            )


def _validate_index_ranges(
    topo: Dict[str, Any], counts: Dict[str, int], bin_data: bytes, prefix: str
) -> None:
    vertices_count = counts["vertices"]
    edges_count = counts["edges"]

    edges = _unpack_u32(topo["edges"], bin_data)
    for idx in edges:
        if idx < 0 or idx >= vertices_count:
            _fail(f"{prefix}.topology.edges: vertex index out of range: {idx} (vertices={vertices_count})")

    corner_vertices = _unpack_u32(topo["corner_vertices"], bin_data)
    for idx in corner_vertices:
        if idx < 0 or idx >= vertices_count:
            _fail(
                f"{prefix}.topology.corner_vertices: vertex index out of range: "
                f"{idx} (vertices={vertices_count})"
            )

    corner_edges = _unpack_u32(topo["corner_edges"], bin_data)
    for idx in corner_edges:
        if idx < 0 or idx >= edges_count:
            _fail(
                f"{prefix}.topology.corner_edges: edge index out of range: "
                f"{idx} (edges={edges_count})"
            )


def _validate_corner_edge_consistency(
    topo: Dict[str, Any], counts: Dict[str, int], bin_data: bytes, prefix: str
) -> None:
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
            if actual != expected:
                _fail(
                    f"{prefix}.topology: corner-edge inconsistency at face {face_index}, "
                    f"corner {c}: edge {edge_idx} has vertices {actual}, expected {expected}"
                )


def _validate_edges(
    topo: Dict[str, Any], counts: Dict[str, int], bin_data: bytes, prefix: str
) -> None:
    """self-edge 및 중복 edge가 없는지 검증한다."""
    if counts["edges"] == 0:
        return

    edges = _unpack_u32(topo["edges"], bin_data)
    seen = set()
    for i in range(0, len(edges), 2):
        v0, v1 = edges[i], edges[i + 1]
        if v0 == v1:
            _fail(
                f"{prefix}.topology.edges: self-edge detected at edge {i // 2}: "
                f"({v0}, {v1})"
            )
        key = (min(v0, v1), max(v0, v1))
        if key in seen:
            _fail(
                f"{prefix}.topology.edges: duplicate edge detected at edge {i // 2}: "
                f"({v0}, {v1})"
            )
        seen.add(key)


def _validate_attributes(mesh: Dict[str, Any], bin_data: bytes, prefix: str) -> None:
    """일반 attribute의 descriptor와 domain/element_count, semantic 일관성을 검증한다."""
    counts = mesh["element_counts"]
    attributes = mesh.get("attributes", [])

    for attr_index, attr in enumerate(attributes):
        attr_prefix = f"{prefix}.attributes[{attr_index}]"
        name = attr.get("name")
        domain = attr.get("domain")
        if domain not in _DOMAIN_COUNT_KEY:
            _fail(f"{attr_prefix}('{name}'): invalid domain '{domain}'")

        expected_elements = counts[_DOMAIN_COUNT_KEY[domain]]
        _validate_descriptor(
            attr["data"],
            bin_data,
            prefix=f"{attr_prefix}('{name}').data",
            expected_component=None,
            expected_count=None,
            expected_elements=expected_elements,
        )

        semantic = attr.get("semantic", "NONE")
        if semantic not in _VALID_SEMANTICS:
            _fail(f"{attr_prefix}('{name}'): invalid semantic '{semantic}'")

        constraints = _SEMANTIC_CONSTRAINTS.get(semantic)
        if constraints is not None:
            component_type = attr["data"]["component_type"]
            component_count = attr["data"]["component_count"]
            if semantic == "COLOR":
                if (component_type, component_count) not in constraints:
                    _fail(
                        f"{attr_prefix}('{name}'): COLOR semantic requires "
                        f"F32x4 or U8x4, got {component_type}x{component_count}"
                    )
            else:
                expected_type, expected_count = constraints
                if component_type != expected_type or component_count != expected_count:
                    _fail(
                        f"{attr_prefix}('{name}'): {semantic} semantic requires "
                        f"{expected_type}x{expected_count}, got {component_type}x{component_count}"
                    )


def _validate_object(obj: Dict[str, Any], mesh_count: int, obj_index: int) -> None:
    prefix = f"objects[{obj_index}]"

    obj_type = obj.get("type")
    if obj_type != "MESH":
        _fail(f"{prefix}: type must be 'MESH', got {obj_type!r}")

    index = obj.get("index")
    if not isinstance(index, int) or index < 0 or index >= mesh_count:
        _fail(f"{prefix}: index {index} is out of range for {mesh_count} meshes")

    transform = obj.get("transform")
    if not isinstance(transform, list) or len(transform) != 16:
        _fail(f"{prefix}: transform must be a list of 16 values, got {transform!r}")


def _unpack_u32(desc: Dict[str, Any], bin_data: bytes) -> list:
    offset = desc["byte_offset"]
    count = desc["element_count"] * desc["component_count"]
    return list(struct.unpack_from(f"<{count}I", bin_data, offset))
