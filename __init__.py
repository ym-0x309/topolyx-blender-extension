import bpy
from bpy.types import TOPBAR_MT_file_export
from bpy.utils import register_class, unregister_class

from . import mattr_export_operator
from . import mattr_properties

classes = [
    mattr_properties.MATTR_PG_export_settings,
    mattr_export_operator.MATTR_OT_export_mesh,
]


def menu_func(self, _context):
    self.layout.operator(
        mattr_export_operator.MATTR_OT_export_mesh.bl_idname,
        text="MATTR (.mattr.json)",
    )


def register():
    for cls in classes:
        register_class(cls)
    TOPBAR_MT_file_export.append(menu_func)


def unregister():
    TOPBAR_MT_file_export.remove(menu_func)
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()
