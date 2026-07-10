"""MATTR 포맷 v0.2.0에 사용하는 데이터 모델."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DataDescriptor:
    """Binary 내 하나의 데이터 배열을 기술한다."""

    byte_offset: int
    byte_length: int
    component_type: str  # "F32" | "I32" | "U32" | "BOOL"
    component_count: int
    element_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "byte_offset": self.byte_offset,
            "byte_length": self.byte_length,
            "component_type": self.component_type,
            "component_count": self.component_count,
            "element_count": self.element_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataDescriptor":
        return cls(
            byte_offset=data["byte_offset"],
            byte_length=data["byte_length"],
            component_type=data["component_type"],
            component_count=data["component_count"],
            element_count=data["element_count"],
        )


@dataclass
class Topology:
    """필수 메시 토폴로지 데이터의 descriptor 집합."""

    positions: DataDescriptor
    edges: DataDescriptor
    corner_vertices: DataDescriptor
    corner_edges: DataDescriptor
    face_offsets: DataDescriptor

    def to_dict(self) -> Dict[str, Any]:
        return {
            "positions": self.positions.to_dict(),
            "edges": self.edges.to_dict(),
            "corner_vertices": self.corner_vertices.to_dict(),
            "corner_edges": self.corner_edges.to_dict(),
            "face_offsets": self.face_offsets.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Topology":
        return cls(
            positions=DataDescriptor.from_dict(data["positions"]),
            edges=DataDescriptor.from_dict(data["edges"]),
            corner_vertices=DataDescriptor.from_dict(data["corner_vertices"]),
            corner_edges=DataDescriptor.from_dict(data["corner_edges"]),
            face_offsets=DataDescriptor.from_dict(data["face_offsets"]),
        )


@dataclass
class ElementCounts:
    """메시의 element 개수."""

    vertices: int
    edges: int
    faces: int
    corners: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "vertices": self.vertices,
            "edges": self.edges,
            "faces": self.faces,
            "corners": self.corners,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "ElementCounts":
        return cls(
            vertices=data["vertices"],
            edges=data["edges"],
            faces=data["faces"],
            corners=data["corners"],
        )


@dataclass
class TopologyData:
    """Binary 직렬화 직전의 토폴로지 배열 데이터."""

    positions: List[float]  # flat F32 array
    edges: List[int]        # flat U32 array
    corner_vertices: List[int]  # flat U32 array
    corner_edges: List[int]     # flat U32 array
    face_offsets: List[int]     # flat U32 array
    element_counts: ElementCounts


@dataclass
class Attribute:
    """MATTR JSON의 meshes[].attributes 항목."""

    name: str
    domain: str  # "POINT" | "EDGE" | "FACE" | "CORNER"
    data: DataDescriptor

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "data": self.data.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Attribute":
        return cls(
            name=data["name"],
            domain=data["domain"],
            data=DataDescriptor.from_dict(data["data"]),
        )


@dataclass
class Mesh:
    """MATTR JSON의 meshes 배열 항목."""

    name: str
    element_counts: ElementCounts
    topology: Topology
    attributes: List[Attribute] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "element_counts": self.element_counts.to_dict(),
            "topology": self.topology.to_dict(),
            "attributes": [attr.to_dict() for attr in self.attributes],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mesh":
        return cls(
            name=data["name"],
            element_counts=ElementCounts.from_dict(data["element_counts"]),
            topology=Topology.from_dict(data["topology"]),
            attributes=[
                Attribute.from_dict(attr) for attr in data.get("attributes", [])
            ],
        )


@dataclass
class ObjectEntry:
    """MATTR JSON의 objects 배열 항목."""

    name: str
    type: str
    index: int
    transform: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "index": self.index,
            "transform": self.transform,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObjectEntry":
        return cls(
            name=data["name"],
            type=data["type"],
            index=data["index"],
            transform=list(data["transform"]),
        )


@dataclass
class Header:
    """MATTR 파일 헤더."""

    format: str = "MATTR"
    version: str = "0.2"

    def to_dict(self) -> Dict[str, str]:
        return {"format": self.format, "version": self.version}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Header":
        return cls(format=data["format"], version=data["version"])


@dataclass
class CoordinateSystem:
    """좌표계 정보."""

    up_axis: str = "+Z"
    forward_axis: str = "+Y"
    handedness: str = "RIGHT"
    winding: str = "CCW"
    meters_per_unit: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "up_axis": self.up_axis,
            "forward_axis": self.forward_axis,
            "handedness": self.handedness,
            "winding": self.winding,
            "meters_per_unit": self.meters_per_unit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoordinateSystem":
        return cls(
            up_axis=data["up_axis"],
            forward_axis=data["forward_axis"],
            handedness=data["handedness"],
            winding=data["winding"],
            meters_per_unit=data["meters_per_unit"],
        )


@dataclass
class Buffer:
    """Binary buffer 메타데이터."""

    uri: str
    byte_length: int

    def to_dict(self) -> Dict[str, Any]:
        return {"uri": self.uri, "byte_length": self.byte_length}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Buffer":
        return cls(uri=data["uri"], byte_length=data["byte_length"])


@dataclass
class MattrFile:
    """전체 MATTR JSON 문서."""

    header: Header
    buffer: Buffer
    coordinate_system: CoordinateSystem
    objects: List[ObjectEntry]
    meshes: List[Mesh]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": self.header.to_dict(),
            "buffer": self.buffer.to_dict(),
            "coordinate_system": self.coordinate_system.to_dict(),
            "objects": [obj.to_dict() for obj in self.objects],
            "meshes": [mesh.to_dict() for mesh in self.meshes],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MattrFile":
        return cls(
            header=Header.from_dict(data["header"]),
            buffer=Buffer.from_dict(data["buffer"]),
            coordinate_system=CoordinateSystem.from_dict(data["coordinate_system"]),
            objects=[ObjectEntry.from_dict(obj) for obj in data["objects"]],
            meshes=[Mesh.from_dict(mesh) for mesh in data["meshes"]],
        )
