"""MATTR Exporter 테스트용 공통 헬퍼."""

import json
import struct
import sys
import tempfile
from pathlib import Path
from typing import Sequence

import bpy

ADDON_MODULE = "blender_mattr_exporter"


def reset_addon():
    """소스 디렉터리의 애드온을 최신 상태로 등록한다."""
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    if ADDON_MODULE in bpy.context.preferences.addons:
        try:
            bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
        except RuntimeError as exc:
            # 이미 설치된 애드온과의 충돌로 인한 unregister 오류는 무시한다.
            print(f"Warning: failed to disable existing addon: {exc}")

    for name in list(sys.modules.keys()):
        if name == ADDON_MODULE or name.startswith(ADDON_MODULE + "."):
            del sys.modules[name]

    import blender_mattr_exporter

    blender_mattr_exporter.register()
    return blender_mattr_exporter


def clear_scene():
    """현재 씬의 모든 오브젝트를 삭제한다."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def select_only(objs: Sequence[bpy.types.Object]) -> None:
    """지정한 오브젝트들만 선택하고 active를 마지막으로 설정한다."""
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objs:
        obj.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[-1]


def export_active_object(
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


def export_selected(
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


def export_all_meshes(tmpdir: Path, name: str, **operator_kwargs) -> tuple[Path, Path]:
    """씬의 모든 메시 오브젝트를 익스포트하고 JSON/bin 경로를 반환한다."""
    json_path = tmpdir / f"{name}.mattr.json"
    result = bpy.ops.export_mesh.mattr(
        filepath=str(json_path), use_selection=False, **operator_kwargs
    )
    assert result == {"FINISHED"}, f"Operator returned {result}"
    bin_path = json_path.with_name(json_path.stem + ".bin")
    return json_path, bin_path


def load_result(json_path: Path, bin_path: Path) -> tuple[dict, bytes]:
    """JSON과 binary 데이터를 읽어 검증 후 반환한다."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    bin_data = bin_path.read_bytes()

    from blender_mattr_exporter import mattr_validator

    mattr_validator.validate_mattr(data, bin_data)
    return data, bin_data


def find_attribute(data: dict, name: str, mesh_index: int = 0) -> dict:
    """data['meshes'][mesh_index]['attributes']에서 이름으로 attribute를 찾는다."""
    for attr in data["meshes"][mesh_index]["attributes"]:
        if attr["name"] == name:
            return attr
    raise AssertionError(f"Attribute '{name}' not found in meshes[{mesh_index}]")


def find_object(data: dict, name: str) -> dict:
    """data['objects']에서 이름으로 object entry를 찾는다."""
    for obj in data["objects"]:
        if obj["name"] == name:
            return obj
    raise AssertionError(f"Object '{name}' not found")


def find_mesh(data: dict, name: str) -> dict:
    """data['meshes']에서 이름으로 mesh entry를 찾는다."""
    for mesh in data["meshes"]:
        if mesh["name"] == name:
            return mesh
    raise AssertionError(f"Mesh '{name}' not found")


def assert_f32_values(bin_data: bytes, desc: dict, expected: Sequence[float]) -> None:
    """binary에서 descriptor 위치의 F32 값이 expected와 일치하는지 확인한다."""
    count = desc["element_count"] * desc["component_count"]
    actual = struct.unpack_from(f"<{count}f", bin_data, desc["byte_offset"])
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected):
        assert abs(a - e) < 1e-6, f"Value mismatch: {a} vs {e}"


def assert_i32_values(bin_data: bytes, desc: dict, expected: Sequence[int]) -> None:
    """binary에서 descriptor 위치의 I32 값이 expected와 일치하는지 확인한다."""
    count = desc["element_count"] * desc["component_count"]
    actual = struct.unpack_from(f"<{count}i", bin_data, desc["byte_offset"])
    assert list(actual) == list(expected)


def assert_u32_values(bin_data: bytes, desc: dict, expected: Sequence[int]) -> None:
    """binary에서 descriptor 위치의 U32 값이 expected와 일치하는지 확인한다."""
    count = desc["element_count"] * desc["component_count"]
    actual = struct.unpack_from(f"<{count}I", bin_data, desc["byte_offset"])
    assert list(actual) == list(expected)


def assert_bool_values(bin_data: bytes, desc: dict, expected: Sequence[int]) -> None:
    """binary에서 descriptor 위치의 BOOL 값이 expected와 일치하는지 확인한다."""
    count = desc["element_count"] * desc["component_count"]
    actual = struct.unpack_from(f"<{count}b", bin_data, desc["byte_offset"])
    assert list(actual) == list(expected)


def tempdir() -> Path:
    """테스트용 임시 디렉터리를 Path 객체로 반환한다."""
    return Path(tempfile.mkdtemp(prefix="mattr_test_"))


def import_mattr_file(json_path: Path, **operator_kwargs) -> None:
    """MATTR 파일을 Import Operator로 불러온다."""
    result = bpy.ops.import_mesh.mattr(filepath=str(json_path), **operator_kwargs)
    assert result == {"FINISHED"}, f"Import operator returned {result}"


def import_topology_only(json_path: Path, bin_path: Path) -> bpy.types.Mesh:
    """MATTR 파일에서 topology만 복원한 Blender Mesh 데이터 블록을 반환한다.

    Attribute 복원은 포함하지 않으며, Phase 8 attribute import 테스트에서
    mesh 생성 부분을 공유하기 위한 헬퍼이다.
    """
    from mathutils import Vector

    from blender_mattr_exporter.mattr_binary import BinaryBufferReader
    from blender_mattr_exporter.mattr_coordinate import CoordinateConverter
    from blender_mattr_exporter.mattr_mesh_import import build_blender_mesh
    from blender_mattr_exporter.mattr_reader import read_mattr

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

    return build_blender_mesh(
        mesh_data.name,
        converted_positions,
        edges,
        corner_vertices,
        corner_edges,
        face_offsets,
        converter.winding,
    )
