"""MATTR import Operator."""

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from . import mattr_importer


class MATTR_OT_import_mesh(Operator, ImportHelper):
    """Import a MATTR file pair into the current Blender scene."""

    bl_idname = "import_mesh.mattr"
    bl_label = "Import MATTR"
    bl_options = {"PRESET", "UNDO"}

    filename_ext = ".mattr.json"

    filter_glob: StringProperty(
        default="*.mattr.json",
        options={"HIDDEN"},
        maxlen=255,
    )

    import_attributes: BoolProperty(
        name="Import Attributes",
        description="Restore mesh attributes such as UV maps, vertex colors, and custom attributes",
        default=True,
    )

    apply_transform: BoolProperty(
        name="Apply Transform",
        description="Bake the object transform into the mesh vertices and reset the object transform",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "import_attributes")
        layout.prop(self, "apply_transform")

    def execute(self, context):
        filepath = _ensure_mattr_json_ext(self.filepath)

        wm = context.window_manager
        wm.progress_begin(0, 100)

        def _update_progress(current: int, total: int) -> None:
            if total > 0:
                wm.progress_update(int((current / total) * 100))

        try:
            warnings = mattr_importer.import_mattr(
                filepath,
                import_attributes=self.import_attributes,
                apply_transform=self.apply_transform,
                progress_callback=_update_progress,
            )
        except mattr_importer.MattrImportError as exc:
            self.report({"ERROR"}, f"MATTR import failed: {exc}")
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"MATTR import failed: {exc}")
            return {"CANCELLED"}
        finally:
            wm.progress_end()

        self._report_warnings(warnings)
        self.report({"INFO"}, f"Imported MATTR from {filepath}")
        return {"FINISHED"}

    def _report_warnings(self, warnings: list[str]) -> None:
        """Expose collected warnings in the Blender UI and console."""
        if not warnings:
            return

        for warning in warnings:
            print(f"MATTR import warning: {warning}")

        if len(warnings) == 1:
            self.report({"WARNING"}, f"MATTR import warning: {warnings[0]}")
        else:
            self.report(
                {"WARNING"},
                f"MATTR import: {len(warnings)} warnings (see console)",
            )


def _ensure_mattr_json_ext(filepath: str) -> str:
    """Ensure the filepath ends with .mattr.json."""
    ext = ".mattr.json"
    if filepath.endswith(ext):
        return filepath
    return bpy.path.ensure_ext(filepath, ext)
