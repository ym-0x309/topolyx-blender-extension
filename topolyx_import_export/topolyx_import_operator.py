"""Topolyx import Operator."""

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from . import topolyx_importer


class TOPOLYX_OT_import_mesh(Operator, ImportHelper):
    """Import a Topolyx `.tlyx` file into the current Blender scene."""

    bl_idname = "import_mesh.tlyx"
    bl_label = "Import Topolyx"
    bl_options = {"PRESET", "UNDO"}

    filename_ext = ".tlyx"

    filter_glob: StringProperty(
        default="*.tlyx",
        options={"HIDDEN"},
        maxlen=255,
    )

    import_attributes: BoolProperty(
        name="Import Attributes",
        description="Restore mesh attributes such as UV maps, vertex colors, and custom attributes",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "import_attributes")

    def execute(self, context):
        filepath = _ensure_tlyx_ext(self.filepath)

        wm = context.window_manager
        wm.progress_begin(0, 100)

        def _update_progress(current: int, total: int) -> None:
            if total > 0:
                wm.progress_update(int((current / total) * 100))

        try:
            warnings = topolyx_importer.import_topolyx(
                filepath,
                import_attributes=self.import_attributes,
                progress_callback=_update_progress,
            )
        except topolyx_importer.TopolyxImportError as exc:
            self.report({"ERROR"}, f"Topolyx import failed: {exc}")
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Topolyx import failed: {exc}")
            return {"CANCELLED"}
        finally:
            wm.progress_end()

        self._report_warnings(warnings)
        self.report({"INFO"}, f"Imported Topolyx from {filepath}")
        return {"FINISHED"}

    def _report_warnings(self, warnings: list[str]) -> None:
        """Expose collected warnings in the Blender UI and console."""
        if not warnings:
            return

        for warning in warnings:
            print(f"Topolyx import warning: {warning}")

        if len(warnings) == 1:
            self.report({"WARNING"}, f"Topolyx import warning: {warnings[0]}")
        else:
            self.report(
                {"WARNING"},
                f"Topolyx import: {len(warnings)} warnings (see console)",
            )


def _ensure_tlyx_ext(filepath: str) -> str:
    """Ensure the filepath ends with .tlyx."""
    ext = ".tlyx"
    if filepath.endswith(ext):
        return filepath
    return bpy.path.ensure_ext(filepath, ext)
