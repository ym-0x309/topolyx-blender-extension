"""Blender Mesh attribute를 Topolyx attribute로 추출한다."""

import array
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import bpy

from .topolyx_types import ElementCounts


@dataclass
class AttributeArrays:
    """Binary 직렬화 직전의 attribute 배열 데이터."""

    name: str
    domain: str  # "POINT" | "EDGE" | "FACE" | "CORNER"
    component_type: str  # "F32" | "I32" | "U32" | "I8" | "U8" | "BOOL"
    component_count: int
    values: List[float] | List[int]
    semantic: str = "NONE"


# Blender data_type → (Topolyx component_type, component_count, foreach_get property)
_BLENDER_TO_TOPOLYX_TYPE_MAP = {
    "FLOAT": ("F32", 1, "value"),
    "INT": ("I32", 1, "value"),
    "INT8": ("I8", 1, "value"),
    "BOOLEAN": ("BOOL", 1, "value"),
    "FLOAT2": ("F32", 2, "vector"),
    "FLOAT_VECTOR": ("F32", 3, "vector"),
    "FLOAT_COLOR": ("F32", 4, "color"),
    "BYTE_COLOR": ("U8", 4, "color"),
    "INT32_2D": ("I32", 2, "value"),
}

# (Topolyx component_type, component_count) → (Blender data_type, foreach_get property)
_TOPOLYX_TO_BLENDER_TYPE_MAP = {
    ("F32", 1): ("FLOAT", "value"),
    ("F32", 2): ("FLOAT2", "vector"),
    ("F32", 3): ("FLOAT_VECTOR", "vector"),
    ("I32", 1): ("INT", "value"),
    ("I32", 2): ("INT32_2D", "value"),
    ("I8", 1): ("INT8", "value"),
    ("U8", 4): ("BYTE_COLOR", "color"),
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

# semantic prefix 기반 매핑에 사용할 접두사 목록
_SEMANTIC_PREFIXES = ("POSITION", "DIRECTION", "NORMAL", "ROTATION", "TANGENT", "COLOR")

# semantic별 허용 (component_type, component_count) 조합. COLOR는 두 가지를 허용한다.
_SEMANTIC_CONSTRAINTS = {
    "POSITION": ("F32", 3),
    "DIRECTION": ("F32", 3),
    "NORMAL": ("F32", 3),
    "ROTATION": ("F32", 4),
    "TANGENT": ("F32", 4),
    "COLOR": {("F32", 4), ("U8", 4)},
}

# Blender 기본 attribute 이름 → Topolyx semantic 자동 매핑
_DEFAULT_SEMANTIC_MAP = {
    "normal": "NORMAL",
    "tangent": "TANGENT",
    "Col": "COLOR",
    "color": "COLOR",
}


def _semantic_is_valid(
    semantic: str, component_type: str, component_count: int
) -> bool:
    """주어진 semantic이 (component_type, component_count) 조합에서 유효한지 확인한다."""
    constraint = _SEMANTIC_CONSTRAINTS.get(semantic)
    if constraint is None:
        return True
    if isinstance(constraint, set):
        return (component_type, component_count) in constraint
    expected_type, expected_count = constraint
    return component_type == expected_type and component_count == expected_count


def _assign_semantic(
    name: str,
    data_type: str,
    component_type: str,
    component_count: int,
    auto_assign_semantics: bool = True,
) -> str:
    """Blender attribute 이름과 data_type에 따라 Topolyx semantic을 결정한다.

    auto_assign_semantics=False이면 모든 attribute의 semantic을 NONE으로 남긴다.
    """
    if not auto_assign_semantics:
        return "NONE"

    semantic: str = "NONE"

    if name in _DEFAULT_SEMANTIC_MAP:
        semantic = _DEFAULT_SEMANTIC_MAP[name]
    else:
        for prefix in _SEMANTIC_PREFIXES:
            if name.startswith(prefix + "_"):
                semantic = prefix
                break

    if semantic == "NONE" and data_type in ("FLOAT_COLOR", "BYTE_COLOR"):
        semantic = "COLOR"

    if semantic != "NONE" and not _semantic_is_valid(
        semantic, component_type, component_count
    ):
        return "NONE"

    return semantic


def _strip_semantic_prefix(name: str) -> str:
    """semantic prefix가 있으면 제거한 이름을 반환한다."""
    for prefix in _SEMANTIC_PREFIXES:
        if name.startswith(prefix + "_"):
            return name[len(prefix) + 1 :]
    return name


def extract_attributes(
    mesh: bpy.types.Mesh,
    counts: ElementCounts,
    export_attributes: bool = True,
    exclude_hidden: bool = True,
    excluded_names: Optional[Set[str]] = None,
    remove_semantic_prefix: bool = False,
    auto_assign_semantics: bool = True,
) -> Tuple[List[AttributeArrays], List[str]]:
    """Blender mesh에서 TOPOLYX로 낳볼 attribute 배열을 추출한다.

    Args:
        auto_assign_semantics: False이면 semantic 자동 할당을 하지 않고 모두 NONE으로 남긴다.

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

        type_info = _BLENDER_TO_TOPOLYX_TYPE_MAP.get(data_type)
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
        semantic = _assign_semantic(
            name,
            data_type,
            component_type,
            component_count,
            auto_assign_semantics=auto_assign_semantics,
        )
        attr_name = _strip_semantic_prefix(name) if remove_semantic_prefix else name

        attributes.append(
            AttributeArrays(
                name=attr_name,
                domain=domain,
                component_type=component_type,
                component_count=component_count,
                values=values,
                semantic=semantic,
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
        # Topolyx U8×4로 저장하기 위해 0~255 범위로 양자화한다.
        buf = array.array("f", [0.0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return [max(0, min(255, int(v * 255.0 + 0.5))) for v in buf]

    component_type = _BLENDER_TO_TOPOLYX_TYPE_MAP[data_type][0]
    if component_type == "F32":
        buf = array.array("f", [0.0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)
    elif component_type == "I32":
        buf = array.array("i", [0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)
    elif component_type == "I8":
        buf = array.array("b", [0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)
    elif component_type == "BOOL":
        # Blender의 BOOLEAN attribute는 foreach_get이 int 0/1을 받는다.
        buf = array.array("b", [0]) * total_count
        attribute.data.foreach_get(prop_name, buf)
        return list(buf)

    raise RuntimeError(f"Unhandled attribute data type: {data_type}")


def topolyx_component_type_to_blender(
    component_type: str, component_count: int, use_byte_color: bool = False
) -> Tuple[str, str]:
    """Topolyx attribute descriptor를 Blender attribute type으로 변환한다.

    U32는 Blender에 unsigned 32-bit attribute type이 없으므로, 비트 패턴을 그대로
    유지한 채 signed 32-bit(INT/INT32_2D)로 해석한다. 이는 의도된 동작이다.

    Returns:
        (blender_data_type, prop_name): Blender attribute 생성 및 쓰기에 사용할
        data_type과 foreach_set/foreach_get property 이름.

    Raises:
        ValueError: 지원하지 않는 (component_type, component_count) 조합일 경우.
    """
    if component_type == "F32" and component_count == 4:
        return "FLOAT_COLOR", "color"

    if component_type == "U8" and component_count == 4:
        return "BYTE_COLOR", "color"

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
    result = _TOPOLYX_TO_BLENDER_TYPE_MAP.get(key)
    if result is None:
        raise ValueError(
            f"Unsupported Topolyx attribute type: ({component_type}, {component_count})"
        )
    return result
