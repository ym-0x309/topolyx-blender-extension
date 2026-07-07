"""Blender Mesh attribute를 MATTR attribute로 추출한다."""

import array
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import bpy

from .mattr_types import ElementCounts


@dataclass
class AttributeArrays:
    """Binary 직렬화 직전의 attribute 배열 데이터."""

    name: str
    domain: str  # "POINT" | "EDGE" | "FACE" | "CORNER"
    component_type: str  # "F32" | "I32" | "U32"
    component_count: int
    values: List[float] | List[int]


# Blender data_type → (MATTR component_type, component_count, foreach_get property)
_ATTRIBUTE_TYPE_MAP = {
    "FLOAT": ("F32", 1, "value"),
    "INT": ("I32", 1, "value"),
    "FLOAT2": ("F32", 2, "vector"),
    "FLOAT_VECTOR": ("F32", 3, "vector"),
    "FLOAT_COLOR": ("F32", 4, "color"),
    "BYTE_COLOR": ("F32", 4, "color"),
    "INT32_2D": ("I32", 2, "vector"),
}

_SUPPORTED_DOMAINS = {"POINT", "EDGE", "FACE", "CORNER"}

# 토폴로지와 중복되거나 난 Outputplus boolean flag. 경고 없이 무시한다.
_SILENTLY_SKIPPED_NAMES = {
    "position",
    "sharp_edge",
    "sharp_face",
    "freestyle_edge",
    "freestyle_face",
}

# domain → element_counts의 필드명
_DOMAIN_COUNT_KEY = {
    "POINT": "vertices",
    "EDGE": "edges",
    "FACE": "faces",
    "CORNER": "corners",
}


def extract_attributes(
    mesh: bpy.types.Mesh,
    counts: ElementCounts,
    export_attributes: bool = True,
    exclude_hidden: bool = True,
    excluded_names: Optional[Set[str]] = None,
) -> Tuple[List[AttributeArrays], List[str]]:
    """Blender mesh에서 MATTR로 낼 장할 attribute 배열을 추출한다.

    Returns:
        (attributes, warnings): 추출된 attribute 목록과 사용자에게 보여줄 경고 메시지 목록
    """
    attributes: List[AttributeArrays] = []
    warnings: List[str] = []

    if not export_attributes:
        return attributes, warnings

    excluded_names = excluded_names or set()

    for attribute in mesh.attributes:
        name = attribute.name
        domain = attribute.domain
        data_type = attribute.data_type

        if exclude_hidden and (name.startswith(".") or name in _SILENTLY_SKIPPED_NAMES):
            continue

        if name in excluded_names:
            continue

        if domain not in _SUPPORTED_DOMAINS:
            warnings.append(
                f"Skipping attribute '{name}': unsupported domain '{domain}'"
            )
            continue

        type_info = _ATTRIBUTE_TYPE_MAP.get(data_type)
        if type_info is None:
            warnings.append(
                f"Skipping attribute '{name}': unsupported data type '{data_type}'"
            )
            continue

        component_type, component_count, prop_name = type_info
        element_count = len(attribute.data)
        expected_count = getattr(counts, _DOMAIN_COUNT_KEY[domain])

        if element_count == 0:
            continue

        if element_count != expected_count:
            warnings.append(
                f"Skipping attribute '{name}': element count mismatch "
                f"({element_count} vs {expected_count})"
            )
            continue

        values = _read_attribute_values(attribute, data_type, component_count, prop_name)
        attributes.append(
            AttributeArrays(
                name=name,
                domain=domain,
                component_type=component_type,
                component_count=component_count,
                values=values,
            )
        )

    return attributes, warnings


def _read_attribute_values(
    attribute: bpy.types.Attribute,
    data_type: str,
    component_count: int,
    prop_name: str,
) -> List[float] | List[int]:
    """attribute.data에서 raw 값을 읽어 flat list로 반환한다."""
    element_count = len(attribute.data)
    total_count = element_count * component_count

    if data_type == "BYTE_COLOR":
        # Blender의 BYTE_COLOR는 API에서 0~1 정규화된 float로 노출된다.
        buf = array.array("f", [0.0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)

    component_type = _ATTRIBUTE_TYPE_MAP[data_type][0]
    if component_type == "F32":
        buf = array.array("f", [0.0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)
    elif component_type == "I32":
        buf = array.array("i", [0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)

    raise RuntimeError(f"Unhandled attribute data type: {data_type}")
