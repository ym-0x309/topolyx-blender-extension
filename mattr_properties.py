import bpy
from bpy.types import PropertyGroup


class MATTR_PG_export_settings(PropertyGroup):
    """Phase 0에서는 빈 PropertyGroup으로만 등록해 둡니다.

    Phase 3~5에서 attribute 필터, 좌표계 옵션 등을 추가할 예정입니다.
    """
    pass
