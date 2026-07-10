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
_BLENDER_TO_MATTR_TYPE_MAP = {
    "FLOAT": ("F32", 1, "value"),
    "INT": ("I32", 1, "value"),
    "BOOLEAN": ("BOOL", 1, "value"),
    "FLOAT2": ("F32", 2, "vector"),
    "FLOAT_VECTOR": ("F32", 3, "vector"),
    "FLOAT_COLOR": ("F32", 4, "color"),
    "BYTE_COLOR": ("F32", 4, "color"),
    "INT32_2D": ("I32", 2, "value"),
}

# (MATTR component_type, component_count) → (Blender data_type, foreach_get property)
_MATTR_TO_BLENDER_TYPE_MAP = {
    ("F32", 1): ("FLOAT", "value"),
    ("F32", 2): ("FLOAT2", "vector"),
    ("F32", 3): ("FLOAT_VECTOR", "vector"),
    ("I32", 1): ("INT", "value"),
    ("I32", 2): ("INT32_2D", "value"),
    ("U32", 1): ("INT", "value"),
    ("U32", 2): ("INT32_2D", "value"),
}

_SUPPORTED_DOMAINS = {"POINT", "EDGE", "FACE", "CORNER"}

# 토폴로지와 중복되거나 Blender 낮부 selection 관련 attribute는 경고 없이 무시한다.
# sharp_edge/face, freestyle_edge/face는 v0.2.0부터 포함 대상이므로 제외함.
_SILENTLY_SKIPPED_NAMES = {
    "position",
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
    """Blender mesh에서 MATTR로 내보낼 attribute 배열을 추출한다.

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

        type_info = _BLENDER_TO_MATTR_TYPE_MAP.get(data_type)
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

    component_type = _BLENDER_TO_MATTR_TYPE_MAP[data_type][0]
    if component_type == "F32":
        buf = array.array("f", [0.0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)
    elif component_type == "I32":
        buf = array.array("i", [0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)
    elif component_type == "BOOL":
        # Blender의 BOOLEAN attribute는 foreach_get이 int 0/1을 받는다.
        buf = array.array("b", [0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)

    raise RuntimeError(f"Unhandled attribute data type: {data_type}")


def mattr_component_type_to_blender(
    component_type: str, component_count: int, use_byte_color: bool = False
) -> Tuple[str, str]:
    """MATTR attribute descriptor를 Blender attribute type으로 변환한다.

    U32는 Blender에 unsigned 32-bit attribute type이 없으므로, 비트 패턴을 그대로
    유지한 채 signed 32-bit(INT/INT32_2D)로 해석한다. 이는 의도된 동작이다.

    Returns:
        (blender_data_type, prop_name): Blender attribute 생성 및 쓰기에 사용할
        data_type과 foreach_set/foreach_get property 이름.

    Raises:
        ValueError: 지원하지 않는 (component_type, component_count) 조합일 경우.
    """
    if component_type == "F32" and component_count == 4:
        if use_byte_color:
            return "BYTE_COLOR", "color"
        return "FLOAT_COLOR", "color"

    if component_type == "BOOL":
        if component_count == 1:
            return "BOOLEAN", "value"
        raise ValueError(
            f"BOOL attribute with component_count {component_count} is not supported; "
            "only BOOLx1 is supported"
        )

    if component_type == "U32":
        # Blender에는 unsigned 32-bit attribute type이 없다.
        # U32 비트 패턴을 그대로 I32로 해석(reinterpret cast)하여 저장한다.
        if component_count == 1:
            return "INT", "value"
        if component_count == 2:
            return "INT32_2D", "value"
        raise ValueError(
            f"U32 attribute with component_count {component_count} is not supported; "
            "only U32x1 and U32x2 can be reinterpreted as I32"
        )

    key = (component_type, component_count)
    result = _MATTR_TO_BLENDER_TYPE_MAP.get(key)
    if result is None:
        raise ValueError(
            f"Unsupported MATTR attribute type: ({component_type}, {component_count})"
        )
    return result
