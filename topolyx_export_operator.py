import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from pathlib import Path

from . import topolyx_validator, topolyx_writer
from .topolyx_coordinate import CoordinateConverter
from .topolyx_types import CoordinateSystem


_AXIS_ITEMS = [
    ("+X", "+X", "Positive X axis"),
    ("-X", "-X", "Negative X axis"),
    ("+Y", "+Y", "Positive Y axis"),
    ("-Y", "-Y", "Negative Y axis"),
    ("+Z", "+Z", "Positive Z axis"),
    ("-Z", "-Z", "Negative Z axis"),
]


class TOPOLYX_OT_export_mesh(Operator, ExportHelper):
    bl_idname = "export_mesh.tlyx"
    bl_label = "Export Topolyx"
    bl_options = {"PRESET"}

    filename_ext = ".tlyx.json"

    filter_glob: StringProperty(
        default="*.tlyx.json",
        options={"HIDDEN"},
        maxlen=255,
    )

    use_selection: BoolProperty(
        name="Selection Only",
        description="Export only selected mesh objects",
        default=True,
    )

    coordinate_system_preset: EnumProperty(
        name="Coordinate System Preset",
        description="Select a preset or choose CUSTOM to configure axes manually",
        items=[
            ("TOPOLYX_DEFAULT", "Topolyx Default", "+Z up, +Y forward, right-handed, CCW"),
            ("BLENDER", "Blender", "+Z up, +Y forward, right-handed, CCW (Blender native)"),
            ("CUSTOM", "Custom", "Manually specify up/forward axes and other options"),
        ],
        default="TOPOLYX_DEFAULT",
    )

    up_axis: EnumProperty(
        name="Up Axis",
        description="Target coordinate system up axis",
        items=_AXIS_ITEMS,
        default="+Z",
    )

    forward_axis: EnumProperty(
        name="Forward Axis",
        description="Target coordinate system forward axis",
        items=_AXIS_ITEMS,
        default="+Y",
    )

    handedness: EnumProperty(
        name="Handedness",
        description="Target coordinate system handedness (left-handed is not supported)",
        items=[
            ("RIGHT", "Right-handed", "Right-handed coordinate system"),
            ("LEFT", "Left-handed", "Left-handed coordinate system (not supported)"),
        ],
        default="RIGHT",
    )

    winding: EnumProperty(
        name="Winding",
        description="Target coordinate system polygon winding order",
        items=[
            ("CCW", "Counter-Clockwise", "Counter-clockwise polygon winding"),
            ("CW", "Clockwise", "Clockwise polygon winding"),
        ],
        default="CCW",
    )

    meters_per_unit: FloatProperty(
        name="Meters per Unit",
        description="Scale factor: how many meters one unit represents in the target coordinate system",
        default=1.0,
        min=0.0001,
        soft_max=1000.0,
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

    remove_semantic_prefix: BoolProperty(
        name="Remove Semantic Prefix",
        description="Strip semantic prefixes (e.g. DIRECTION_) from attribute names in the exported file",
        default=False,
    )

    def check(self, _context):
        """다중 확장자(.tlyx.json)가 중복되지 않도록 filepath를 보정한다."""
        import os

        filepath = self.filepath
        if not os.path.basename(filepath):
            return False

        ext = ".tlyx.json"
        if filepath.endswith(ext):
            return False

        # 사용자가 .json이나 .tlyx까지만 입력한 경우 깔끔하게 재구성
        if filepath.endswith(".json"):
            filepath = filepath[:-5]
        elif filepath.endswith(".tlyx"):
            filepath = filepath[:-6]

        new_filepath = bpy.path.ensure_ext(filepath, ext)
        if new_filepath != self.filepath:
            self.filepath = new_filepath
            return True
        return False

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_selection")

        box = layout.box()
        box.label(text="Coordinate System")
        box.prop(self, "coordinate_system_preset")
        custom = self.coordinate_system_preset == "CUSTOM"
        sub = box.column()
        sub.enabled = custom
        sub.prop(self, "up_axis")
        sub.prop(self, "forward_axis")
        sub.prop(self, "handedness")
        sub.prop(self, "winding")
        sub.prop(self, "meters_per_unit")

        layout.prop(self, "export_attributes")
        if self.export_attributes:
            box = layout.box()
            box.label(text="Attribute Options")
            box.prop(self, "exclude_hidden_attributes")
            box.prop(self, "excluded_attribute_names")
            box.prop(self, "remove_semantic_prefix")

    def execute(self, context):
        if self.use_selection:
            target_objects = list(context.selected_objects)
        else:
            target_objects = list(context.scene.objects)

        mesh_objects = [obj for obj in target_objects if obj.type == "MESH"]

        warnings: list[str] = []
        for obj in target_objects:
            if obj.type != "MESH":
                warnings.append(f"skipping non-mesh object '{obj.name}'")

        if not mesh_objects:
            self.report({"ERROR"}, "No mesh objects to export")
            return {"CANCELLED"}

        coordinate_system = self._build_coordinate_system()
        if coordinate_system.handedness == "LEFT":
            self.report(
                {"ERROR"},
                "Left-handed coordinate systems are not supported by this extension",
            )
            return {"CANCELLED"}

        try:
            CoordinateConverter(coordinate_system)
        except ValueError as exc:
            self.report({"ERROR"}, f"Invalid coordinate system: {exc}")
            return {"CANCELLED"}

        self.filepath = _ensure_topolyx_json_ext(self.filepath)
        json_path = Path(self.filepath)
        bin_path = json_path.with_name(json_path.stem + ".bin")

        wm = context.window_manager
        wm.progress_begin(0, len(mesh_objects))

        def _update_progress(processed_count: int) -> None:
            wm.progress_update(processed_count)

        try:
            writer_warnings = topolyx_writer.write_topolyx(
                self.filepath,
                mesh_objects,
                coordinate_system,
                export_attributes=self.export_attributes,
                exclude_hidden_attributes=self.exclude_hidden_attributes,
                excluded_attribute_names=self.excluded_attribute_names,
                remove_semantic_prefix=self.remove_semantic_prefix,
                progress_callback=_update_progress,
            )
            warnings.extend(writer_warnings)

            topolyx_validator.validate_topolyx_file(self.filepath)
        except topolyx_validator.TopolyxValidationError as exc:
            _delete_export_files(json_path, bin_path)
            self.report({"ERROR"}, f"Topolyx validation failed: {exc}")
            return {"CANCELLED"}
        except Exception as exc:
            # Writer already cleans up on write failure; this catches any other error.
            _delete_export_files(json_path, bin_path)
            self.report({"ERROR"}, f"Topolyx export failed: {exc}")
            return {"CANCELLED"}
        finally:
            wm.progress_end()

        self._report_warnings(warnings)
        self.report({"INFO"}, f"Exported Topolyx to {self.filepath}")
        return {"FINISHED"}

    def _report_warnings(self, warnings: list[str]) -> None:
        """수집된 경고를 Blender UI와 콘솔에 노출한다."""
        if not warnings:
            return

        for warning in warnings:
            print(f"Topolyx export warning: {warning}")

        # UI에는 핵심 내용만 요약 리포트 (Blender report는 너무 길면 잘림)
        if len(warnings) == 1:
            self.report({"WARNING"}, f"Topolyx export warning: {warnings[0]}")
        else:
            self.report(
                {"WARNING"},
                f"Topolyx export: {len(warnings)} warnings (see console)",
            )

    def _build_coordinate_system(self) -> CoordinateSystem:
        """Operator 설정으로부터 CoordinateSystem 객체를 생성한다."""
        if self.coordinate_system_preset == "BLENDER":
            return CoordinateSystem(
                up_axis="+Z",
                forward_axis="+Y",
                handedness="RIGHT",
                winding="CCW",
                meters_per_unit=1.0,
            )
        if self.coordinate_system_preset == "TOPOLYX_DEFAULT":
            return CoordinateSystem(
                up_axis="+Z",
                forward_axis="+Y",
                handedness="RIGHT",
                winding="CCW",
                meters_per_unit=1.0,
            )
        return CoordinateSystem(
            up_axis=self.up_axis,
            forward_axis=self.forward_axis,
            handedness=self.handedness,
            winding=self.winding,
            meters_per_unit=self.meters_per_unit,
        )


def _ensure_topolyx_json_ext(filepath: str) -> str:
    """filepath가 .tlyx.json로 끝나도록 보정한다."""
    ext = ".tlyx.json"
    if filepath.endswith(ext):
        return filepath
    if filepath.endswith(".json"):
        return filepath[:-5] + ext
    if filepath.endswith(".tlyx"):
        return filepath + ".json"
    return filepath + ext


def _delete_export_files(json_path: Path, bin_path: Path) -> None:
    """익스포트 도중 생성된 파일 쌍을 삭제한다."""
    json_path.unlink(missing_ok=True)
    bin_path.unlink(missing_ok=True)
