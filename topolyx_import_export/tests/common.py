"""Topolyx Import/Export 테스트용 공통 헬퍼."""

import json
import struct
import sys
import tempfile
from pathlib import Path
from typing import Sequence

import bpy

ADDON_MODULE = "topolyx_import_export"


def reset_addon():
    """프로젝트 루트(익스텐션 디렉터리)에 있는 소스를 애드온으로 등록한다.

    topolyx_import_export 패키지를 이름으로 임포트할 수 있도록
    프로젝트 루트를 sys.path에 추가한다.
    """
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root.parent))

    if ADDON_MODULE in bpy.context.preferences.addons:
        try:
            bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
        except RuntimeError as exc:
            # 이미 설치된 애드온과의 충돌로 인한 unregister 오류는 무시한다.
            print(f"Warning: failed to disable existing addon: {exc}")

    for name in list(sys.modules.keys()):
        if name == ADDON_MODULE or name.startswith(ADDON_MODULE + "."):
            del sys.modules[name]

    import topolyx_import_export

    topolyx_import_export.register()
    return topolyx_import_export


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


def export_active_object(tmpdir: Path, name: str, **operator_kwargs) -> Path:
    """현재 active object를 익스포트하고 .tlyx 파일 경로를 반환한다."""
    obj = bpy.context.active_object
    if obj is not None:
        obj.select_set(True)
    tlyx_path = tmpdir / f"{name}.tlyx"
    result = bpy.ops.export_mesh.tlyx(filepath=str(tlyx_path), **operator_kwargs)
    assert result == {"FINISHED"}, f"Operator returned {result}"
    return tlyx_path


def export_selected(tmpdir: Path, name: str, **operator_kwargs) -> Path:
    """현재 선택된 오브젝트들을 익스포트하고 .tlyx 파일 경로를 반환한다."""
    tlyx_path = tmpdir / f"{name}.tlyx"
    result = bpy.ops.export_mesh.tlyx(
        filepath=str(tlyx_path), use_selection=True, **operator_kwargs
    )
    assert result == {"FINISHED"}, f"Operator returned {result}"
    return tlyx_path


def export_all_meshes(tmpdir: Path, name: str, **operator_kwargs) -> Path:
    """씬의 모든 메시 오브젝트를 익스포트하고 .tlyx 파일 경로를 반환한다."""
    tlyx_path = tmpdir / f"{name}.tlyx"
    result = bpy.ops.export_mesh.tlyx(
        filepath=str(tlyx_path), use_selection=False, **operator_kwargs
    )
    assert result == {"FINISHED"}, f"Operator returned {result}"
    return tlyx_path


def load_result(tlyx_path: Path) -> tuple[dict, bytes]:
    """.tlyx 파일에서 JSON 메타데이터와 binary 데이터를 분리해 검증 후 반환한다."""
    from topolyx_import_export.topolyx_binary import read_tlyx_container
    from topolyx_import_export import topolyx_validator

    container_data = tlyx_path.read_bytes()
    json_bytes, bin_data = read_tlyx_container(container_data)
    data = json.loads(json_bytes.decode("utf-8"))

    topolyx_validator.validate_topolyx(data, bin_data)
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
    return Path(tempfile.mkdtemp(prefix="topolyx_test_"))


def import_topolyx_file(tlyx_path: Path, **operator_kwargs) -> None:
    """Topolyx .tlyx 파일을 Import Operator로 불러온다."""
    result = bpy.ops.import_mesh.tlyx(filepath=str(tlyx_path), **operator_kwargs)
    assert result == {"FINISHED"}, f"Import operator returned {result}"


def import_topology_only(tlyx_path: Path) -> bpy.types.Mesh:
    """Topolyx .tlyx 파일에서 topology만 복원한 Blender Mesh 데이터 블록을 반환한다.

    Attribute 복원은 포함하지 않으며, Phase 8 attribute import 테스트에서
    mesh 생성 부분을 공유하기 위한 헬퍼이다.
    """
    from mathutils import Vector

    from topolyx_import_export.topolyx_binary import BinaryBufferReader
    from topolyx_import_export.topolyx_coordinate import CoordinateConverter
    from topolyx_import_export.topolyx_mesh_import import build_blender_mesh
    from topolyx_import_export.topolyx_reader import read_topolyx

    topolyx_file, bin_data = read_topolyx(tlyx_path)
    mesh_data = topolyx_file.meshes[0]
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
        topolyx_file.coordinate_system
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
    )
