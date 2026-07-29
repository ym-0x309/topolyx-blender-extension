"""Phase 2 테스트 — 좌표계 변환 및 Object Transform 변환 검증.

Usage:
    blender -b -P tests/test_phase2.py
"""

import struct
import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트(익스텐션 디렉터리)를 패키지로 임포트할 수 있도록 상위 디렉터리를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy
from mathutils import Matrix, Vector

from topolyx_import_export.topolyx_coordinate import CoordinateConverter
from topolyx_import_export.tests import common


def test_default_cube_topolyx_default():
    """TOPOLYX_DEFAULT preset으로 Default Cube를 익스포트했을 때 좌표 변환이 적용되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_active_object(
            tmpdir,
            "cube_topolyx_default",
            meters_per_unit=1.0,
            export_attributes=False,
        )
        data, bin_data = common.load_result(tlyx_path)

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

        # Blender와 TOPOLYX_DEFAULT는 동일한 좌표계(up=+Z, forward=+Y)이므로
        # 좌표 변환이 일어나지 않는다.
        first_x, first_y, first_z = positions[0], positions[1], positions[2]
        assert abs(first_x - (-1.0)) < 1e-6
        assert abs(first_y - (-1.0)) < 1e-6
        assert abs(first_z - (-1.0)) < 1e-6
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_default_cube_topolyx_default passed")


def test_transformed_cube_topolyx_default():
    """TOPOLYX_DEFAULT preset에서 transform translation이 변환되지 않고 유지되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))
    obj = bpy.context.active_object
    obj.rotation_euler = (0.1, 0.2, 0.3)

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_active_object(
            tmpdir,
            "transformed_cube_topolyx_default",
            meters_per_unit=1.0,
            export_attributes=False,
        )
        data, bin_data = common.load_result(tlyx_path)

        transform = data["objects"][0]["transform"]
        assert len(transform) == 16
        # Blender와 TOPOLYX_DEFAULT는 동일한 좌표계이므로 변환 없이 (1, 2, 3) 유지
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
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_transformed_cube_topolyx_default passed")


def test_blender_preset_unchanged():
    """BLENDER preset은 Phase 1과 동일한 동작을 한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_active_object(
            tmpdir,
            "cube_blender",
            meters_per_unit=1.0,
            export_attributes=False,
        )
        data, bin_data = common.load_result(tlyx_path)

        cs = data["coordinate_system"]
        assert cs["forward_axis"] == "+Y"

        transform = data["objects"][0]["transform"]
        assert abs(transform[12] - 1.0) < 1e-6
        assert abs(transform[13] - 2.0) < 1e-6
        assert abs(transform[14] - 3.0) < 1e-6
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_blender_preset_unchanged passed")


def test_face_offsets_order():
    """face_offsets가 polygon 인덱스 순서대로 contiguous하게 생성되는지 확인한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("OrderedFaceMesh")
    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    faces = [(0, 1, 2), (0, 2, 3)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new("OrderedFaceObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        tlyx_path = common.export_active_object(
            tmpdir,
            "ordered_faces",
            meters_per_unit=1.0,
            export_attributes=False,
        )
        data, bin_data = common.load_result(tlyx_path)

        topo = data["meshes"][0]["topology"]
        face_offsets = struct.unpack_from(
            f"<{topo['face_offsets']['element_count']}I",
            bin_data,
            topo["face_offsets"]["byte_offset"],
        )
        # polygon[0]은 3개 corner, polygon[1]은 3개 corner
        assert face_offsets == (0, 3, 6), f"Unexpected face_offsets: {face_offsets}"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_face_offsets_order passed")


def test_coordinate_converter_matrix():
    """CoordinateConverter.convert_matrix가 meters_per_unit 스케일을 수행하는지 확인한다."""
    converter = CoordinateConverter("TOPOLYX_DEFAULT")

    # Topolyx v1.0.0은 Blender와 동일한 고정 좌표계이므로 translation 변환 없음
    T = Matrix.Translation(Vector((1, 2, 3)))
    converted = converter.convert_matrix(T)
    translation = converted.to_translation()
    assert abs(translation.x - 1.0) < 1e-6
    assert abs(translation.y - 2.0) < 1e-6
    assert abs(translation.z - 3.0) < 1e-6

    # BLENDER preset도 동일한 고정 좌표계를 사용
    blender_converter = CoordinateConverter("BLENDER")
    converted_id = blender_converter.convert_matrix(T)
    t = converted_id.to_translation()
    assert abs(t.x - 1.0) < 1e-6
    assert abs(t.y - 2.0) < 1e-6
    assert abs(t.z - 3.0) < 1e-6

    print("test_coordinate_converter_matrix passed")


def main():
    common.reset_addon()
    test_default_cube_topolyx_default()
    test_transformed_cube_topolyx_default()
    test_blender_preset_unchanged()
    test_face_offsets_order()
    test_coordinate_converter_matrix()
    print("All Phase 2 tests passed")


if __name__ == "__main__":
    main()
