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

    def check(self, _context):
        """다중 확장자(.mattr.json)가 중복되지 않도록 filepath를 보정한다."""
        import os

        filepath = self.filepath
        if not os.path.basename(filepath):
            return False

        ext = ".mattr.json"
        if filepath.endswith(ext):
            return False

        # 사용자가 .json이나 .mattr까지만 입력한 경우 깔끔하게 재구성
        if filepath.endswith(".json"):
            filepath = filepath[:-5]
        elif filepath.endswith(".mattr"):
            filepath = filepath[:-6]

        new_filepath = bpy.path.ensure_ext(filepath, ext)
        if new_filepath != self.filepath:
            self.filepath = new_filepath
            return True
        return False

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "No active mesh object selected")
            return {"CANCELLED"}

        self.filepath = _ensure_mattr_json_ext(self.filepath)

        try:
            mattr_writer.write_mattr(self.filepath, obj)
        except Exception as exc:
            self.report({"ERROR"}, f"MATTR export failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Exported MATTR to {self.filepath}")
        return {"FINISHED"}


def _ensure_mattr_json_ext(filepath: str) -> str:
    """filepath가 .mattr.json로 끝나도록 보정한다."""
    ext = ".mattr.json"
    if filepath.endswith(ext):
        return filepath
    if filepath.endswith(".json"):
        return filepath[:-5] + ext
    if filepath.endswith(".mattr"):
        return filepath + ".json"
    return filepath + ext
