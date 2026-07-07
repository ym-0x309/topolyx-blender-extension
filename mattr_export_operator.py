import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty
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

    use_selection: BoolProperty(
        name="Selection Only",
        description="Export only selected mesh objects",
        default=True,
    )

    coordinate_system_preset: EnumProperty(
        name="Coordinate System",
        description="Target coordinate system for the exported file",
        items=[
            ("MATTR_DEFAULT", "MATTR Default", "+Z up, +Y forward (spec example)"),
            ("BLENDER", "Blender", "+Z up, +Y forward (Blender native)"),
        ],
        default="MATTR_DEFAULT",
    )

    export_attributes: BoolProperty(
        name="Export Attributes",
        description="Export mesh attributes such as UV maps, vertex colors, and custom attributes",
        default=True,
    )

    exclude_hidden_attributes: BoolProperty(
        name="Exclude Hidden/Internal Attributes",
        description="Skip attributes with names starting with '.' and known internal attributes such as 'position'",
        default=True,
    )

    excluded_attribute_names: StringProperty(
        name="Excluded Attributes",
        description="Comma-separated list of attribute names to skip during export",
        default="",
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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_selection")
        layout.prop(self, "coordinate_system_preset")
        layout.prop(self, "export_attributes")
        if self.export_attributes:
            layout.prop(self, "exclude_hidden_attributes")
            layout.prop(self, "excluded_attribute_names")

    def execute(self, context):
        if self.use_selection:
            target_objects = list(context.selected_objects)
        else:
            target_objects = list(context.scene.objects)

        mesh_objects = [obj for obj in target_objects if obj.type == "MESH"]

        for obj in target_objects:
            if obj.type != "MESH":
                print(f"MATTR export warning: skipping non-mesh object '{obj.name}'")

        if not mesh_objects:
            self.report({"ERROR"}, "No mesh objects to export")
            return {"CANCELLED"}

        self.filepath = _ensure_mattr_json_ext(self.filepath)

        try:
            mattr_writer.write_mattr(
                self.filepath,
                mesh_objects,
                self.coordinate_system_preset,
                export_attributes=self.export_attributes,
                exclude_hidden_attributes=self.exclude_hidden_attributes,
                excluded_attribute_names=self.excluded_attribute_names,
            )
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
