"""MATTR file pair importer core."""

from pathlib import Path
from typing import Callable, List, Optional, Sequence

import bpy
from mathutils import Matrix, Vector

from .mattr_attribute_import import apply_attributes
from .mattr_binary import BinaryBufferReader
from .mattr_coordinate import CoordinateConverter
from .mattr_mesh_import import build_blender_mesh
from .mattr_reader import read_mattr
from .mattr_types import MattrFile, Mesh, ObjectEntry
from .mattr_utils import column_major_list_to_matrix


class MattrImportError(Exception):
    """Fatal error raised during MATTR import."""

    pass


def import_mattr(
    filepath: str | Path,
    import_attributes: bool = True,
    apply_transform: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[str]:
    """Import a MATTR file pair into the current Blender scene.

    Args:
        filepath: Path to the .mattr.json file. A .mattr.bin with the same
            basename must exist in the same directory.
        import_attributes: Whether to restore mesh attributes.
        apply_transform: If True, bake the object world matrix into the mesh
            vertices and reset the object transform to identity. Shared meshes
            are duplicated when this option is enabled.
        progress_callback: Optional callback receiving (current_step, total_steps).

    Returns:
        List of warning messages collected during import.

    Raises:
        MattrImportError: If a fatal error occurs during import.
    """
    filepath = Path(filepath)

    try:
        mattr_file, bin_data = read_mattr(filepath)
    except Exception as exc:
        raise MattrImportError(f"Failed to read MATTR file: {exc}") from exc

    converter = CoordinateConverter.from_coordinate_system(
        mattr_file.coordinate_system
    )

    created_meshes: list[bpy.types.Mesh] = []
    created_objects: list[bpy.types.Object] = []
    warnings: list[str] = []

    total_steps = len(mattr_file.meshes) + len(mattr_file.objects)

    def _report_progress(current: int) -> None:
        if progress_callback is not None:
            progress_callback(current, total_steps)

    mesh_map: dict[int, bpy.types.Mesh] = {}
    mesh_usage: dict[int, int] = {}

    try:
        for mesh_index, mesh_data in enumerate(mattr_file.meshes):
            mesh = _build_mesh(
                mesh_data,
                bin_data,
                converter,
                import_attributes,
                warnings,
            )
            created_meshes.append(mesh)
            mesh_map[mesh_index] = mesh
            _report_progress(mesh_index + 1)

        for obj_index, obj_data in enumerate(mattr_file.objects):
            obj = _create_object(
                obj_data,
                mesh_map[obj_data.index],
                converter,
                apply_transform,
                mesh_usage,
                created_meshes,
                warnings,
            )
            created_objects.append(obj)
            _report_progress(len(mattr_file.meshes) + obj_index + 1)

        _select_imported_objects(created_objects)
    except Exception as exc:
        _cleanup_import(created_objects, created_meshes)
        raise MattrImportError(f"MATTR import failed: {exc}") from exc

    return warnings


def _build_mesh(
    mesh_data: Mesh,
    bin_data: bytes,
    converter: CoordinateConverter,
    import_attributes: bool,
    warnings: List[str],
) -> bpy.types.Mesh:
    """Build a Blender Mesh data block from a MATTR mesh entry."""
    reader = BinaryBufferReader(bin_data)
    topo = mesh_data.topology

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

    converted_positions = _convert_positions(positions, converter)

    mesh = build_blender_mesh(
        name=mesh_data.name or "ImportedMesh",
        positions=converted_positions,
        edges=edges,
        corner_vertices=corner_vertices,
        corner_edges=corner_edges,
        face_offsets=face_offsets,
        winding=converter.winding,
    )

    if import_attributes:
        attr_warnings = apply_attributes(mesh, mesh_data.attributes, bin_data)
        warnings.extend(attr_warnings)

    return mesh


def _convert_positions(
    positions: Sequence[float], converter: CoordinateConverter
) -> List[float]:
    """Convert a flat F32 position array from file space to Blender space."""
    converted: list[float] = []
    for i in range(0, len(positions), 3):
        v = converter.inverse_convert_position(
            Vector((positions[i], positions[i + 1], positions[i + 2]))
        )
        converted.extend((v.x, v.y, v.z))
    return converted


def _create_object(
    obj_data: ObjectEntry,
    source_mesh: bpy.types.Mesh,
    converter: CoordinateConverter,
    apply_transform: bool,
    mesh_usage: dict[int, int],
    created_meshes: List[bpy.types.Mesh],
    warnings: List[str],
) -> bpy.types.Object:
    """Create a Blender Object from a MATTR object entry and link it to the scene."""
    mesh = source_mesh
    file_mesh_index = obj_data.index

    if apply_transform:
        if mesh_usage.get(file_mesh_index, 0) > 0:
            mesh = source_mesh.copy()
            created_meshes.append(mesh)
        mesh_usage[file_mesh_index] = mesh_usage.get(file_mesh_index, 0) + 1

    obj = bpy.data.objects.new(obj_data.name or "ImportedObject", mesh)

    collection = bpy.context.view_layer.active_layer_collection.collection
    collection.objects.link(obj)

    blender_matrix = column_major_list_to_matrix(obj_data.transform)
    blender_matrix = converter.inverse_convert_matrix(blender_matrix)
    obj.matrix_world = blender_matrix

    if apply_transform:
        _apply_transform_to_mesh(mesh, blender_matrix)
        obj.matrix_world = Matrix.Identity(4)

    return obj


def _apply_transform_to_mesh(mesh: bpy.types.Mesh, matrix: Matrix) -> None:
    """Apply a world matrix to all vertex coordinates of a mesh in-place."""
    for vertex in mesh.vertices:
        vertex.co = matrix @ vertex.co
    mesh.update()


def _select_imported_objects(objects: Sequence[bpy.types.Object]) -> None:
    """Select the imported objects and set the last one as active."""
    if not objects:
        return

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[-1]


def _cleanup_import(
    objects: Sequence[bpy.types.Object],
    meshes: Sequence[bpy.types.Mesh],
) -> None:
    """Remove objects and meshes created during a failed import."""
    for obj in objects:
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

    for mesh in meshes:
        if mesh.name in bpy.data.meshes:
            bpy.data.meshes.remove(mesh)
