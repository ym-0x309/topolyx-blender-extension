"""Phase 7 테스트 — MATTR topology 배열의 Blender Mesh 복원 검증.

Usage:
    blender -b -P blender_mattr_exporter/tests/test_phase7.py
"""

import json
import sys
from pathlib import Path

# 개별 실행 시 프로젝트 루트를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import bpy
from mathutils import Vector

from blender_mattr_exporter.mattr_binary import BinaryBufferReader
from blender_mattr_exporter.mattr_coordinate import CoordinateConverter
from blender_mattr_exporter.mattr_mesh_import import build_blender_mesh
from blender_mattr_exporter.mattr_reader import read_mattr
from blender_mattr_exporter.tests import common


def _read_topology_arrays(json_path: Path, bin_path: Path):
    """익스포트된 파일에서 topology 배열과 winding을 읽어 반환한다."""
    mattr_file, bin_data = read_mattr(json_path)
    mesh_data = mattr_file.meshes[0]
    topo = mesh_data.topology
    reader = BinaryBufferReader(bin_data)

    positions = list(
        reader.read_f32(
            topo.positions.byte_offset,
            topo.positions.element_count * topo.positions.component_count,
        )
    )
    edges = list(
        reader.read_u32(
            topo.edges.byte_offset,
            topo.edges.element_count * topo.edges.component_count,
        )
    )
    corner_vertices = list(
        reader.read_u32(
            topo.corner_vertices.byte_offset,
            topo.corner_vertices.element_count
            * topo.corner_vertices.component_count,
        )
    )
    corner_edges = list(
        reader.read_u32(
            topo.corner_edges.byte_offset,
            topo.corner_edges.element_count * topo.corner_edges.component_count,
        )
    )
    face_offsets = list(
        reader.read_u32(
            topo.face_offsets.byte_offset,
            topo.face_offsets.element_count * topo.face_offsets.component_count,
        )
    )

    converter = CoordinateConverter.from_coordinate_system(
        mattr_file.coordinate_system
    )
    converted_positions = []
    for i in range(0, len(positions), 3):
        v = converter.inverse_convert_position(
            Vector((positions[i], positions[i + 1], positions[i + 2]))
        )
        converted_positions.extend((v.x, v.y, v.z))

    return (
        converted_positions,
        edges,
        corner_vertices,
        corner_edges,
        face_offsets,
        converter.winding,
    )


def _assert_topology_matches(
    mesh: bpy.types.Mesh,
    positions,
    edges,
    corner_vertices,
    corner_edges,
    face_offsets,
    winding=None,
):
    """생성된 mesh의 topology가 원본 배열과 일치하는지 확인한다."""
    assert len(mesh.vertices) == len(positions) // 3
    assert len(mesh.edges) == len(edges) // 2
    assert len(mesh.polygons) == len(face_offsets) - 1
    assert len(mesh.loops) == len(corner_vertices)

    for i, vertex in enumerate(mesh.vertices):
        expected = Vector((positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]))
        assert (vertex.co - expected).length < 1e-5

    for i, edge in enumerate(mesh.edges):
        v0, v1 = edges[i * 2], edges[i * 2 + 1]
        assert {edge.vertices[0], edge.vertices[1]} == {v0, v1}

    for loop, expected_vertex, expected_edge in zip(
        mesh.loops, corner_vertices, corner_edges
    ):
        assert loop.vertex_index == expected_vertex
        assert loop.edge_index == expected_edge

    expected_face_offsets = [poly.loop_start for poly in mesh.polygons]
    expected_face_offsets.append(len(mesh.loops))
    assert expected_face_offsets == list(face_offsets)


def test_default_cube_topology():
    """Default Cube의 topology가 round-trip으로 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "cube", export_attributes=False
        )
        arrays = _read_topology_arrays(json_path, bin_path)
        mesh = build_blender_mesh("ImportedCube", *arrays)
        _assert_topology_matches(mesh, *arrays)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_default_cube_topology passed")


def test_empty_mesh_topology():
    """빈 메시의 topology가 복원되는지 확인한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("EmptyMesh")
    obj = bpy.data.objects.new("EmptyObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "empty", export_attributes=False
        )
        arrays = _read_topology_arrays(json_path, bin_path)
        imported_mesh = build_blender_mesh("ImportedEmpty", *arrays)
        assert len(imported_mesh.vertices) == 0
        assert len(imported_mesh.edges) == 0
        assert len(imported_mesh.polygons) == 0
        assert len(imported_mesh.loops) == 0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_empty_mesh_topology passed")


def test_loose_vertex_topology():
    """Loose vertex를 포함한 메시의 topology가 복원되는지 확인한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("LooseVertexMesh")
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    mesh.from_pydata(verts, [], [])
    mesh.update()
    obj = bpy.data.objects.new("LooseVertexObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "loose_vertex", export_attributes=False
        )
        arrays = _read_topology_arrays(json_path, bin_path)
        imported_mesh = build_blender_mesh("ImportedLooseVertex", *arrays)
        _assert_topology_matches(imported_mesh, *arrays)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_loose_vertex_topology passed")


def test_loose_edge_topology():
    """Loose edge를 포함한 메시의 topology가 복원되는지 확인한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("LooseEdgeMesh")
    verts = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
    edges = [(0, 1), (2, 0)]
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    obj = bpy.data.objects.new("LooseEdgeObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "loose_edge", export_attributes=False
        )
        arrays = _read_topology_arrays(json_path, bin_path)
        imported_mesh = build_blender_mesh("ImportedLooseEdge", *arrays)
        _assert_topology_matches(imported_mesh, *arrays)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_loose_edge_topology passed")


def test_ngon_topology():
    """N-gon 메시의 topology가 복원되는지 확인한다."""
    common.clear_scene()
    bpy.ops.mesh.primitive_circle_add(vertices=5, fill_type="NGON", radius=1)

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "ngon", export_attributes=False
        )
        arrays = _read_topology_arrays(json_path, bin_path)
        imported_mesh = build_blender_mesh("ImportedNgon", *arrays)
        _assert_topology_matches(imported_mesh, *arrays)
        assert len(imported_mesh.polygons) == 1
        assert len(imported_mesh.polygons[0].loop_indices) == 5
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_ngon_topology passed")


def test_mixed_faces_topology():
    """Triangle, quad, ngon이 혼합된 메시의 topology가 복원되는지 확인한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("MixedMesh")
    verts = [
        (0, 0, 0),
        (2, 0, 0),
        (2, 2, 0),
        (0, 2, 0),
        (1, 3, 0),
        (3, 3, 0),
    ]
    faces = [(0, 1, 2, 3), (2, 3, 4), (2, 4, 5)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("MixedObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "mixed", export_attributes=False
        )
        arrays = _read_topology_arrays(json_path, bin_path)
        imported_mesh = build_blender_mesh("ImportedMixed", *arrays)
        _assert_topology_matches(imported_mesh, *arrays)
        assert len(imported_mesh.polygons) == 3
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_mixed_faces_topology passed")


def test_cw_winding_reversal():
    """CW winding 파일을 import하면 face corner 순서가 reverse되는지 확인한다."""
    common.clear_scene()
    mesh = bpy.data.meshes.new("CwMesh")
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    mesh.from_pydata(verts, [], [(0, 1, 2)])
    mesh.update()
    obj = bpy.data.objects.new("CwObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    tmpdir = common.tempdir()
    try:
        json_path, bin_path = common.export_active_object(
            tmpdir, "cw_source", export_attributes=False
        )

        # JSON의 winding을 CW로 변경
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["coordinate_system"]["winding"] = "CW"
        cw_json_path = tmpdir / "cw_source.mattr.json"
        with open(cw_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        arrays = _read_topology_arrays(cw_json_path, bin_path)
        imported_mesh = build_blender_mesh("ImportedCW", *arrays)

        assert len(imported_mesh.polygons) == 1
        assert len(imported_mesh.loops) == 3

        # CCW 파일이었다면 [0,1,2] 순서였겠지만, CW이므로 reverse되어 [2,1,0]
        loop_vertices = [loop.vertex_index for loop in imported_mesh.loops]
        assert loop_vertices == [2, 1, 0], f"Unexpected loop vertices: {loop_vertices}"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_cw_winding_reversal passed")


def main():
    common.reset_addon()
    test_default_cube_topology()
    test_empty_mesh_topology()
    test_loose_vertex_topology()
    test_loose_edge_topology()
    test_ngon_topology()
    test_mixed_faces_topology()
    test_cw_winding_reversal()
    print("All Phase 7 tests passed")


if __name__ == "__main__":
    main()
