import bpy
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper

from . import mattr_writer


class MATTR_OT_export_mesh(Operator, ExportHelper):
    bl_idname = "export_mesh.mattr"
    bl_label = "Export MATTR"
    bl_options = {"PRESET"}

    filename_ext = ".mattr.json"

    filter_glob: StringProperty(
        default="*.mattr.json",
        options={"HIDDEN"},
        maxlen=255,
    )

    use_setting: BoolProperty(
        name="Example Option",
        description="Placeholder option for future export settings",
        default=True,
    )

    def execute(self, _context):
        self.report({"INFO"}, f"Export path: {self.filepath}")
        # Phase 1에서 실제 쓰기 로직을 연결할 예정입니다.
        # mattr_writer.write_mattr(self.filepath)
        return {"FINISHED"}
