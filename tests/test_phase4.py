"""Phase 4 테스트 — 다중 오브젝트 및 메시 공유 검증.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase4.py
"""

import json
import struct
import sys
import tempfile
from pathlib import Path

import bpy

ADDON_MODULE = "blender_mattr_exporter"


def _reset_addon():
    """소스 디렉터리의 애드온을 최신 상태로 등록한다."""
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    if ADDON_MODULE in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)

    for name in list(sys.modules.keys()):
        if name == ADDON_MODULE or name.startswith(ADDON_MODULE + "."):
            del sys.modules[name]

    import blender_mattr_exporter

    blender_mattr_exporter.register()
    return blender_mattr_exporter


def _clear_scene():
    """현재 씬의 모든 오브젝트를 삭제한다."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _select_only(objs):
    """지정한 오브젝트들만 선택하고 active를 마지막으로 설정한다."""
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objs:
        obj.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[-1]


def _export_selected(
    tmpdir: Path, name: str, **operator_kwargs
) -> tuple[Path, Path]:
    """현재 선택된 오브젝트들을 익스포트하고 JSON/bin 경로를 반환한다."""
    json_path = tmpdir / f"{name}.mattr.json"
    result = bpy.ops.export_mesh.mattr(
        filepath=str(json_path), use_selection=True, **operator_kwargs
    )
    assert result == {"FINISHED"}, f"Operator returned {result}"
    bin_path = json_path.with_name(json_path.stem + ".bin")
    return json_path, bin_path


def _load_result(json_path: Path, bin_path: Path):
    """JSON과 binary 데이터를 읽어 반환한다."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    bin_data = bin_path.read_bytes()

    from blender_mattr_exporter import mattr_validator

    mattr_validator.validate_mattr(data, bin_data)
    return data, bin_data


def _find_object(data, name):
    """data['objects']에서 이름으로 object entry를 찾는다."""
    for obj in data["objects"]:
        if obj["name"] == name:
            return obj
    raise AssertionError(f"Object '{name}' not found")


def _find_mesh(data, name):
    """data['meshes']에서 이름으로 mesh entry를 찾는다."""
    for mesh in data["meshes"]:
        if mesh["name"] == name:
            return mesh
    raise AssertionError(f"Mesh '{name}' not found")


def test_two_separate_meshes():
    """서로 다른 메시를 가진 두 오브젝트를 익스포트하면 objects 2개, meshes 2개가 생성된다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object

    _select_only([cube, sphere])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_selected(tmpdir, "two_meshes")
        data, bin_data = _load_result(json_path, bin_path)

        assert len(data["objects"]) == 2
        assert len(data["meshes"]) == 2

        cube_obj = _find_object(data, cube.name)
        sphere_obj = _find_object(data, sphere.name)
        assert cube_obj["index"] != sphere_obj["index"]

        cube_mesh = data["meshes"][cube_obj["index"]]
        sphere_mesh = data["meshes"][sphere_obj["index"]]
        assert cube_mesh["element_counts"]["vertices"] == 8
        assert sphere_mesh["element_counts"]["vertices"] > 8

    print("test_two_separate_meshes passed")


def test_linked_duplicate_shared_mesh():
    """링크 복제한 두 오브젝트는 같은 mesh index를 참조한다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    original = bpy.context.active_object

    # 링크 복제
    bpy.ops.object.duplicate_move_linked(
        OBJECT_OT_duplicate={"linked": True, "mode": "INIT"},
        TRANSFORM_OT_translate={"value": (3, 0, 0)},
    )
    duplicate = bpy.context.active_object

    _select_only([original, duplicate])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_selected(tmpdir, "linked_dup")
        data, bin_data = _load_result(json_path, bin_path)

        assert len(data["objects"]) == 2
        assert len(data["meshes"]) == 1

        original_obj = _find_object(data, original.name)
        duplicate_obj = _find_object(data, duplicate.name)
        assert original_obj["index"] == duplicate_obj["index"] == 0

        # transform translation이 서로 달라야 한다.
        orig_t = original_obj["transform"][12:15]
        dup_t = duplicate_obj["transform"][12:15]
        assert orig_t != dup_t, f"Transforms should differ: {orig_t} vs {dup_t}"

    print("test_linked_duplicate_shared_mesh passed")


def test_selection_only():
    """use_selection=True일 때 선택되지 않은 오브젝트는 익스포트되지 않는다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object

    _select_only([cube])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_selected(tmpdir, "selection_only")
        data, bin_data = _load_result(json_path, bin_path)

        assert len(data["objects"]) == 1
        assert data["objects"][0]["name"] == cube.name

    print("test_selection_only passed")


def test_export_all_meshes():
    """use_selection=False일 때 씬의 모든 메시 오브젝트가 익스포트된다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object

    # 둘 다 선택 해제
    _select_only([])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path = tmpdir / "all_meshes.mattr.json"
        result = bpy.ops.export_mesh.mattr(
            filepath=str(json_path), use_selection=False, export_attributes=False
        )
        assert result == {"FINISHED"}, f"Operator returned {result}"
        bin_path = json_path.with_name(json_path.stem + ".bin")

        data, bin_data = _load_result(json_path, bin_path)

        assert len(data["objects"]) == 2
        object_names = {obj["name"] for obj in data["objects"]}
        assert cube.name in object_names
        assert sphere.name in object_names

    print("test_export_all_meshes passed")


def test_non_mesh_skipped():
    """비메시 오브젝트는 경고 후 무시되고 메시 오브젝트만 익스포트된다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    bpy.ops.object.camera_add(location=(3, 0, 0))
    camera = bpy.context.active_object
    bpy.ops.object.light_add(type="POINT", location=(0, 3, 0))
    light = bpy.context.active_object

    _select_only([cube, camera, light])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_selected(tmpdir, "skip_non_mesh")
        data, bin_data = _load_result(json_path, bin_path)

        assert len(data["objects"]) == 1
        assert data["objects"][0]["name"] == cube.name

    print("test_non_mesh_skipped passed")


def test_shared_mesh_attributes():
    """공유 메시의 attribute는 meshes[0]에 한 번만 기록된다."""
    _clear_scene()
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

    _select_only([original, duplicate])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_selected(tmpdir, "shared_attrs")
        data, bin_data = _load_result(json_path, bin_path)

        assert len(data["objects"]) == 2
        assert len(data["meshes"]) == 1

        mesh_data = data["meshes"][0]
        attr_names = {attr["name"] for attr in mesh_data["attributes"]}
        assert "SharedPointFloat" in attr_names

        shared_attr = next(
            attr for attr in mesh_data["attributes"] if attr["name"] == "SharedPointFloat"
        )
        desc = shared_attr["data"]
        actual = struct.unpack_from(
            f"<{desc['element_count']}f", bin_data, desc["byte_offset"]
        )
        assert list(actual) == values

    print("test_shared_mesh_attributes passed")


def test_empty_mesh_in_multi():
    """빈 메시를 포함한 여러 오브젝트도 정상적으로 익스포트된다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object

    empty_mesh = bpy.data.meshes.new("EmptyMesh")
    empty_obj = bpy.data.objects.new("EmptyObject", empty_mesh)
    bpy.context.collection.objects.link(empty_obj)

    _select_only([cube, empty_obj])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_selected(tmpdir, "with_empty")
        data, bin_data = _load_result(json_path, bin_path)

        assert len(data["objects"]) == 2
        assert len(data["meshes"]) == 2

        empty_mesh_data = _find_mesh(data, "EmptyMesh")
        assert empty_mesh_data["element_counts"] == {
            "vertices": 0,
            "edges": 0,
            "faces": 0,
            "corners": 0,
        }
        assert empty_mesh_data["topology"]["face_offsets"]["element_count"] == 1

    print("test_empty_mesh_in_multi passed")


def main():
    _reset_addon()
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
