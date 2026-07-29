import bpy
from bpy.types import TOPBAR_MT_file_export, TOPBAR_MT_file_import
from bpy.utils import register_class, unregister_class

from . import mattr_export_operator, mattr_import_operator

classes = [
    mattr_export_operator.MATTR_OT_export_mesh,
    mattr_import_operator.MATTR_OT_import_mesh,
]


def menu_func_export(self, _context):
    self.layout.operator(
        mattr_export_operator.MATTR_OT_export_mesh.bl_idname,
        text="MATTR (.mattr.json)",
    )


def menu_func_import(self, _context):
    self.layout.operator(
        mattr_import_operator.MATTR_OT_import_mesh.bl_idname,
        text="MATTR (.mattr.json)",
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


if __name__ == "__main__":
    register()
