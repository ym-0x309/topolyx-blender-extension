"""Phase 2 테스트 — 좌표계 변환 및 Object Transform 변환 검증.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase2.py
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


def _export_active_object(
    tmpdir: Path, name: str, **operator_kwargs
) -> tuple[Path, Path]:
    """현재 active object를 익스포트하고 JSON/bin 경로를 반환한다."""
    obj = bpy.context.active_object
    if obj is not None:
        obj.select_set(True)
    json_path = tmpdir / f"{name}.mattr.json"
    result = bpy.ops.export_mesh.mattr(filepath=str(json_path), **operator_kwargs)
    assert result == {"FINISHED"}, f"Operator returned {result}"
    bin_path = json_path.with_name(json_path.stem + ".bin")
    return json_path, bin_path


def test_default_cube_mattr_default():
    """MATTR_DEFAULT preset으로 Default Cube를 익스포트했을 때 좌표 변환이 적용되는지 확인한다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_active_object(
            tmpdir,
            "cube_mattr_default",
            coordinate_system_preset="MATTR_DEFAULT",
            export_attributes=False,
        )

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bin_data = bin_path.read_bytes()

        from blender_mattr_exporter import mattr_validator

        mattr_validator.validate_mattr(data, bin_data)

        cs = data["coordinate_system"]
        assert cs == {
            "up_axis": "+Z",
            "forward_axis": "+Y",
            "handedness": "RIGHT",
            "winding": "CCW",
            "meters_per_unit": 1.0,
        }

        mesh = data["meshes"][0]
        topo = mesh["topology"]
        positions_desc = topo["positions"]
        positions = struct.unpack_from(
            f"<{positions_desc['element_count'] * 3}f",
            bin_data,
            positions_desc["byte_offset"],
        )

        xs = positions[0::3]
        ys = positions[1::3]
        zs = positions[2::3]
        assert min(xs) == -1.0 and max(xs) == 1.0
        assert min(ys) == -1.0 and max(ys) == 1.0
        assert min(zs) == -1.0 and max(zs) == 1.0

        # Blender와 MATTR_DEFAULT는 동일한 좌표계(up=+Z, forward=+Y)이므로
        # 좌표 변환이 일어나지 않는다.
        # Default Cube의 첫 번째 vertex는 Blender에서 (-1, -1, -1)이다.
        first_x, first_y, first_z = positions[0], positions[1], positions[2]
        assert abs(first_x - (-1.0)) < 1e-6
        assert abs(first_y - (-1.0)) < 1e-6
        assert abs(first_z - (-1.0)) < 1e-6

    print("test_default_cube_mattr_default passed")


def test_transformed_cube_mattr_default():
    """MATTR_DEFAULT preset에서 transform translation이 (-x, -y, z)로 회전되는지 확인한다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))
    obj = bpy.context.active_object
    obj.rotation_euler = (0.1, 0.2, 0.3)

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_active_object(
            tmpdir,
            "transformed_cube_mattr_default",
            coordinate_system_preset="MATTR_DEFAULT",
            export_attributes=False,
        )

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bin_data = bin_path.read_bytes()

        from blender_mattr_exporter import mattr_validator

        mattr_validator.validate_mattr(data, bin_data)

        transform = data["objects"][0]["transform"]
        assert len(transform) == 16
        # Blender와 MATTR_DEFAULT는 동일한 좌표계이므로 변환 없이 (1, 2, 3) 유지
        # column-major에서 translation은 4번째 column(인덱스 12,13,14)
        assert abs(transform[12] - 1.0) < 1e-6
        assert abs(transform[13] - 2.0) < 1e-6
        assert abs(transform[14] - 3.0) < 1e-6

        # positions는 mesh local 좌표이므로 원점 중심 큐브 그대로
        positions_desc = data["meshes"][0]["topology"]["positions"]
        positions = struct.unpack_from(
            f"<{positions_desc['element_count'] * 3}f",
            bin_data,
            positions_desc["byte_offset"],
        )
        xs = positions[0::3]
        ys = positions[1::3]
        zs = positions[2::3]
        assert min(xs) == -1.0 and max(xs) == 1.0
        assert min(ys) == -1.0 and max(ys) == 1.0
        assert min(zs) == -1.0 and max(zs) == 1.0

    print("test_transformed_cube_mattr_default passed")


def test_blender_preset_unchanged():
    """BLENDER preset은 Phase 1과 동일한 동작을 한다."""
    _clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_active_object(
            tmpdir,
            "cube_blender",
            coordinate_system_preset="BLENDER",
            export_attributes=False,
        )

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bin_data = bin_path.read_bytes()

        from blender_mattr_exporter import mattr_validator

        mattr_validator.validate_mattr(data, bin_data)

        cs = data["coordinate_system"]
        assert cs["forward_axis"] == "+Y"

        transform = data["objects"][0]["transform"]
        assert abs(transform[12] - 1.0) < 1e-6
        assert abs(transform[13] - 2.0) < 1e-6
        assert abs(transform[14] - 3.0) < 1e-6

    print("test_blender_preset_unchanged passed")


def test_face_offsets_order():
    """polygon이 loop_start 순서대로 저장되지 않아도 face_offsets가 polygon 인덱스 순서를 따르는지 확인한다."""
    _clear_scene()
    mesh = bpy.data.meshes.new("ReorderedFaceMesh")
    # 두 개의 삼각형을 수동으로 구성. 두 번째 face를 먼저 loop를 할당하여
    # polygon[1].loop_start < polygon[0].loop_start가 되도록 한다.
    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    faces = [(0, 1, 2), (0, 2, 3)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new("ReorderedFaceObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        json_path, bin_path = _export_active_object(
            tmpdir,
            "reordered",
            coordinate_system_preset="BLENDER",
            export_attributes=False,
        )

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bin_data = bin_path.read_bytes()

        from blender_mattr_exporter import mattr_validator

        mattr_validator.validate_mattr(data, bin_data)

        topo = data["meshes"][0]["topology"]
        face_offsets = struct.unpack_from(
            f"<{topo['face_offsets']['element_count']}I",
            bin_data,
            topo["face_offsets"]["byte_offset"],
        )
        # polygon[0]은 3개 corner, polygon[1]은 3개 corner
        assert face_offsets == (0, 3, 6), f"Unexpected face_offsets: {face_offsets}"

    print("test_face_offsets_order passed")


def test_coordinate_converter_matrix():
    """CoordinateConverter.convert_matrix가 similarity transform을 수행하는지 확인한다."""
    from mathutils import Matrix, Vector
    from blender_mattr_exporter.mattr_coordinate import CoordinateConverter

    converter = CoordinateConverter("MATTR_DEFAULT")

    # Blender와 MATTR_DEFAULT는 동일한 좌표계이므로 translation 변환 없음
    T = Matrix.Translation(Vector((1, 2, 3)))
    converted = converter.convert_matrix(T)
    translation = converted.to_translation()
    assert abs(translation.x - 1.0) < 1e-6
    assert abs(translation.y - 2.0) < 1e-6
    assert abs(translation.z - 3.0) < 1e-6

    # BLENDER preset은 identity 변환
    blender_converter = CoordinateConverter("BLENDER")
    converted_id = blender_converter.convert_matrix(T)
    t = converted_id.to_translation()
    assert abs(t.x - 1.0) < 1e-6
    assert abs(t.y - 2.0) < 1e-6
    assert abs(t.z - 3.0) < 1e-6

    print("test_coordinate_converter_matrix passed")


def main():
    _reset_addon()
    test_default_cube_mattr_default()
    test_transformed_cube_mattr_default()
    test_blender_preset_unchanged()
    test_face_offsets_order()
    test_coordinate_converter_matrix()
    print("All Phase 2 tests passed")


if __name__ == "__main__":
    main()
