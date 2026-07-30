import bpy
from bpy.types import TOPBAR_MT_file_export, TOPBAR_MT_file_import
from bpy.utils import register_class, unregister_class

from . import topolyx_export_operator, topolyx_import_operator

classes = [
    topolyx_export_operator.TOPOLYX_OT_export_mesh,
    topolyx_import_operator.TOPOLYX_OT_import_mesh,
]


def menu_func_export(self, _context):
    self.layout.operator(
        topolyx_export_operator.TOPOLYX_OT_export_mesh.bl_idname,
        text="Topolyx (.tlyx)",
    )


def menu_func_import(self, _context):
    self.layout.operator(
        topolyx_import_operator.TOPOLYX_OT_import_mesh.bl_idname,
        text="Topolyx (.tlyx)",
    )


def register():
    for cls in classes:
        register_class(cls)
    TOPBAR_MT_file_export.append(menu_func_export)
    TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    TOPBAR_MT_file_import.remove(menu_func_import)
    TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(classes):
        unregister_class(cls)
