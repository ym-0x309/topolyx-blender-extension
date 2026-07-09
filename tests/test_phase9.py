"""Phase 9 tests — MATTR importer core validation.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase9.py
"""

import sys
from pathlib import Path

# Individual execution support
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy
from mathutils import Vector

from blender_mattr_exporter.mattr_importer import import_mattr
from blender_mattr_exporter.tests import common


def _get_imported_objects():
    """Return all objects in the current scene.

    Tests clear the scene before import, so any remaining objects are imports.
    """
    return list(bpy.context.scene.objects)


def test_import_default_cube_roundtrip():
    """Default Cube export -> import preserves topology and transform."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))
    original_obj = bpy.context.active_object
    original_obj.rotation_euler = (0.1, 0.2, 0.3)

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "cube_roundtrip")
        common.clear_scene()

        warnings = import_mattr(json_path)
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_objs = _get_imported_objects()
        assert len(imported_objs) == 1, f"Expected 1 imported object, got {len(imported_objs)}"
        imported_obj = imported_objs[0]

        mesh = imported_obj.data
        assert len(mesh.vertices) == 8
        assert len(mesh.edges) == 12
        assert len(mesh.polygons) == 6
        assert len(mesh.loops) == 24

        # Transform should be approximately preserved
        loc = imported_obj.matrix_world.to_translation()
        assert (loc - Vector((1.0, 2.0, 3.0))).length < 1e-4
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_default_cube_roundtrip passed")


def test_import_multi_object():
    """Multiple objects are imported into the scene."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object

    common.select_only([cube, sphere])

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_selected(tmpdir, "two_objects")
        common.clear_scene()

        warnings = import_mattr(json_path)
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_objs = _get_imported_objects()
        assert len(imported_objs) == 2, f"Expected 2 imported objects, got {len(imported_objs)}"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_multi_object passed")


def test_import_shared_mesh():
    """Linked duplicate objects share the same Blender mesh after import."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    original = bpy.context.active_object

    bpy.ops.object.duplicate_move_linked(
        OBJECT_OT_duplicate={"linked": True, "mode": "INIT"},
        TRANSFORM_OT_translate={"value": (3, 0, 0)},
    )
    duplicate = bpy.context.active_object

    common.select_only([original, duplicate])

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_selected(tmpdir, "linked_dup")
        common.clear_scene()

        warnings = import_mattr(json_path)
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_objs = _get_imported_objects()
        assert len(imported_objs) == 2

        mesh_a = imported_objs[0].data
        mesh_b = imported_objs[1].data
        assert mesh_a == mesh_b, "Shared mesh should reference the same data block"

        loc_a = imported_objs[0].matrix_world.to_translation()
        loc_b = imported_objs[1].matrix_world.to_translation()
        assert (loc_a - loc_b).length > 1e-4, "Transforms should differ"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_shared_mesh passed")


def test_apply_transform_false_preserves_transform():
    """apply_transform=False keeps object matrix and shared mesh."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "no_apply")
        common.clear_scene()

        warnings = import_mattr(json_path, apply_transform=False)
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_obj = _get_imported_objects()[0]
        loc = imported_obj.matrix_world.to_translation()
        assert (loc - Vector((1.0, 2.0, 3.0))).length < 1e-4

        # Vertices should still be in local space (centered around origin)
        xs = [v.co.x for v in imported_obj.data.vertices]
        assert min(xs) == -1.0 and max(xs) == 1.0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_apply_transform_false_preserves_transform passed")


def test_apply_transform_true_bakes_transform():
    """apply_transform=True bakes matrix into vertices and resets object matrix."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "apply_t")
        common.clear_scene()

        warnings = import_mattr(json_path, apply_transform=True)
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_obj = _get_imported_objects()[0]
        assert imported_obj.matrix_world == imported_obj.matrix_world.Identity(
            4
        ), "Object matrix should be identity"

        # Vertices should be in world space (translated)
        xs = [v.co.x for v in imported_obj.data.vertices]
        assert min(xs) >= 0.0 and max(xs) >= 1.0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_apply_transform_true_bakes_transform passed")


def test_apply_transform_true_duplicates_shared_mesh():
    """apply_transform=True duplicates shared meshes so each object can be baked."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    original = bpy.context.active_object

    bpy.ops.object.duplicate_move_linked(
        OBJECT_OT_duplicate={"linked": True, "mode": "INIT"},
        TRANSFORM_OT_translate={"value": (3, 0, 0)},
    )
    duplicate = bpy.context.active_object

    common.select_only([original, duplicate])

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_selected(tmpdir, "linked_apply")
        common.clear_scene()

        warnings = import_mattr(json_path, apply_transform=True)
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_objs = _get_imported_objects()
        assert len(imported_objs) == 2

        mesh_a = imported_objs[0].data
        mesh_b = imported_objs[1].data
        assert mesh_a != mesh_b, "Shared mesh should be duplicated when applying transform"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_apply_transform_true_duplicates_shared_mesh passed")


def test_import_empty_mesh():
    """An empty mesh object is imported into the scene."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("EmptyMesh")
    obj = bpy.data.objects.new("EmptyObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "empty_import")
        common.clear_scene()

        warnings = import_mattr(json_path)
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_objs = _get_imported_objects()
        assert len(imported_objs) == 1
        imported_mesh = imported_objs[0].data
        assert len(imported_mesh.vertices) == 0
        assert len(imported_mesh.edges) == 0
        assert len(imported_mesh.polygons) == 0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_empty_mesh passed")


def test_import_attributes_disabled():
    """import_attributes=False skips attribute restoration."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data
    values = [float(i) for i in range(len(mesh.vertices))]
    attr = mesh.attributes.new(name="PointFloat", type="FLOAT", domain="POINT")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "no_attrs_import")
        common.clear_scene()

        warnings = import_mattr(json_path, import_attributes=False)
        assert not warnings, f"Unexpected warnings: {warnings}"

        imported_obj = _get_imported_objects()[0]
        assert "PointFloat" not in imported_obj.data.attributes
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_attributes_disabled passed")


def test_import_reserved_attribute_name_renamed():
    """Reserved attribute names are renamed with a prefix and produce warnings."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    mesh = bpy.context.active_object.data
    values = [float(i) for i in range(len(mesh.vertices))]
    attr = mesh.attributes.new(name="MyCustom", type="FLOAT", domain="POINT")
    attr.data.foreach_set("value", values)
    mesh.update()

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(tmpdir, "reserved_import")

        # Modify JSON to use reserved name
        import json

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["meshes"][0]["attributes"][0]["name"] = "position"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        common.clear_scene()
        warnings = import_mattr(json_path)
        assert any("position" in w for w in warnings), f"Expected warning about reserved name, got {warnings}"

        imported_obj = _get_imported_objects()[0]
        assert "import_position" in imported_obj.data.attributes
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_reserved_attribute_name_renamed passed")


def test_import_selects_objects():
    """Imported objects are selected and the last one is active."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object

    common.select_only([cube, sphere])

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_selected(tmpdir, "selection_test")
        common.clear_scene()

        import_mattr(json_path)

        imported_objs = _get_imported_objects()
        assert all(obj.select_get() for obj in imported_objs)
        assert bpy.context.active_object in imported_objs
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_import_selects_objects passed")


def main():
    common.reset_addon()
    test_import_default_cube_roundtrip()
    test_import_multi_object()
    test_import_shared_mesh()
    test_apply_transform_false_preserves_transform()
    test_apply_transform_true_bakes_transform()
    test_apply_transform_true_duplicates_shared_mesh()
    test_import_empty_mesh()
    test_import_attributes_disabled()
    test_import_reserved_attribute_name_renamed()
    test_import_selects_objects()
    print("All Phase 9 tests passed")


if __name__ == "__main__":
    main()
