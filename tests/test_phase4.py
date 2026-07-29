"""Phase 4 테스트 — 다중 오브젝트 및 메시 공유 검증.

Usage:
    blender -b -P tests/test_phase4.py
"""

import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트(익스텐션 디렉터리)를 패키지로 임포트할 수 있도록 상위 디렉터리를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy

from topolyx_import_export.tests import common


def test_two_separate_meshes():
    """서로 다른 메시를 가진 두 오브젝트를 익스포트하면 objects 2개, meshes 2개가 생성된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object

    common.select_only([cube, sphere])

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_selected(tmpdir, "two_meshes")
        data, bin_data = common.load_result(tlyx_path)

        assert len(data["objects"]) == 2
        assert len(data["meshes"]) == 2

        cube_obj = common.find_object(data, cube.name)
        sphere_obj = common.find_object(data, sphere.name)
        assert cube_obj["index"] != sphere_obj["index"]

        cube_mesh = data["meshes"][cube_obj["index"]]
        sphere_mesh = data["meshes"][sphere_obj["index"]]
        assert cube_mesh["element_counts"]["vertices"] == 8
        assert sphere_mesh["element_counts"]["vertices"] > 8
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_two_separate_meshes passed")


def test_linked_duplicate_shared_mesh():
    """링크 복제한 두 오브젝트는 같은 mesh index를 참조한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    original = bpy.context.active_object

    # 링크 복제
    bpy.ops.object.duplicate_move_linked(
        OBJECT_OT_duplicate={"linked": True, "mode": "INIT"},
        TRANSFORM_OT_translate={"value": (3, 0, 0)},
    )
    duplicate = bpy.context.active_object

    common.select_only([original, duplicate])

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_selected(tmpdir, "linked_dup")
        data, bin_data = common.load_result(tlyx_path)

        assert len(data["objects"]) == 2
        assert len(data["meshes"]) == 1

        original_obj = common.find_object(data, original.name)
        duplicate_obj = common.find_object(data, duplicate.name)
        assert original_obj["index"] == duplicate_obj["index"] == 0

        # transform translation이 서로 달라야 한다.
        orig_t = original_obj["transform"][12:15]
        dup_t = duplicate_obj["transform"][12:15]
        assert orig_t != dup_t, f"Transforms should differ: {orig_t} vs {dup_t}"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_linked_duplicate_shared_mesh passed")


def test_selection_only():
    """use_selection=True일 때 선택되지 않은 오브젝트는 익스포트되지 않는다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object

    common.select_only([cube])

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_selected(tmpdir, "selection_only")
        data, bin_data = common.load_result(tlyx_path)

        assert len(data["objects"]) == 1
        assert data["objects"][0]["name"] == cube.name
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_selection_only passed")


def test_export_all_meshes():
    """use_selection=False일 때 씬의 모든 메시 오브젝트가 익스포트된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object

    # 둘 다 선택 해제
    common.select_only([])

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_all_meshes(
            tmpdir, "all_meshes", export_attributes=False
        )
        data, bin_data = common.load_result(tlyx_path)

        assert len(data["objects"]) == 2
        object_names = {obj["name"] for obj in data["objects"]}
        assert cube.name in object_names
        assert sphere.name in object_names
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_export_all_meshes passed")


def test_non_mesh_skipped():
    """비메시 오브젝트는 경고 후 무시되고 메시 오브젝트만 익스포트된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.object.camera_add(location=(3, 0, 0))
    camera = bpy.context.active_object
    bpy.ops.object.light_add(type="POINT", location=(0, 3, 0))
    light = bpy.context.active_object

    common.select_only([cube, camera, light])

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_selected(tmpdir, "skip_non_mesh")
        data, bin_data = common.load_result(tlyx_path)

        assert len(data["objects"]) == 1
        assert data["objects"][0]["name"] == cube.name
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_non_mesh_skipped passed")


def test_shared_mesh_attributes():
    """공유 메시의 attribute는 meshes[0]에 한 번만 기록된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    original = bpy.context.active_object
    mesh = original.data

    values = [float(i) for i in range(len(mesh.vertices))]
    attr = mesh.attributes.new(name="SharedPointFloat", type="FLOAT", domain="POINT")
    attr.data.foreach_set("value", values)
    mesh.update()

    bpy.ops.object.duplicate_move_linked(
        OBJECT_OT_duplicate={"linked": True, "mode": "INIT"},
        TRANSFORM_OT_translate={"value": (3, 0, 0)},
    )
    duplicate = bpy.context.active_object

    common.select_only([original, duplicate])

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_selected(tmpdir, "shared_attrs")
        data, bin_data = common.load_result(tlyx_path)

        assert len(data["objects"]) == 2
        assert len(data["meshes"]) == 1

        mesh_data = data["meshes"][0]
        attr_names = {attr["name"] for attr in mesh_data["attributes"]}
        assert "SharedPointFloat" in attr_names

        shared_attr = common.find_attribute(data, "SharedPointFloat", mesh_index=0)
        desc = shared_attr["data"]
        common.assert_f32_values(bin_data, desc, values)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_shared_mesh_attributes passed")


def test_empty_mesh_in_multi():
    """빈 메시를 포함한 여러 오브젝트도 정상적으로 익스포트된다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object

    empty_mesh = bpy.data.meshes.new("EmptyMeshPhase4")
    empty_obj = bpy.data.objects.new("EmptyObject", empty_mesh)
    bpy.context.collection.objects.link(empty_obj)

    common.select_only([cube, empty_obj])

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_selected(tmpdir, "with_empty")
        data, bin_data = common.load_result(tlyx_path)

        assert len(data["objects"]) == 2
        assert len(data["meshes"]) == 2

        empty_mesh_data = common.find_mesh(data, "EmptyMeshPhase4")
        assert empty_mesh_data["element_counts"] == {
            "vertices": 0,
            "edges": 0,
            "faces": 0,
            "corners": 0,
        }
        assert empty_mesh_data["topology"]["face_offsets"]["element_count"] == 1
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_empty_mesh_in_multi passed")


def main():
    common.reset_addon()
    test_two_separate_meshes()
    test_linked_duplicate_shared_mesh()
    test_selection_only()
    test_export_all_meshes()
    test_non_mesh_skipped()
    test_shared_mesh_attributes()
    test_empty_mesh_in_multi()
    print("All Phase 4 tests passed")


if __name__ == "__main__":
    main()
