"""Blender 좌표계와 MATTR 목표 좌표계 사이를 양방향으로 변환하는 유틸리티."""

from typing import Dict, Optional

from mathutils import Matrix, Vector

from .mattr_types import CoordinateSystem


_AXIS_VECTORS = {
    "+X": Vector((1.0, 0.0, 0.0)),
    "-X": Vector((-1.0, 0.0, 0.0)),
    "+Y": Vector((0.0, 1.0, 0.0)),
    "-Y": Vector((0.0, -1.0, 0.0)),
    "+Z": Vector((0.0, 0.0, 1.0)),
    "-Z": Vector((0.0, 0.0, -1.0)),
}

_PRESETS: Dict[str, CoordinateSystem] = {
    "BLENDER": CoordinateSystem(
        up_axis="+Z",
        forward_axis="+Y",
        handedness="RIGHT",
        winding="CCW",
    ),
    "MATTR_DEFAULT": CoordinateSystem(
        up_axis="+Z",
        forward_axis="+Y",
        handedness="RIGHT",
        winding="CCW",
    ),
}


class CoordinateConverter:
    """Blender coordinate system과 target coordinate system 사이를 양방향으로 변환한다.

    변환 행렬 M은 ``p_target = M @ p_blender``를 만족하도록 정의한다.
    ``meters_per_unit``이 1.0이 아닌 경우, 위치 변환에 단위 스케일도 함께 적용한다.

    Blender world matrix를 target world matrix로 변환할 때는
    ``M_target = S^-1 @ M @ M_blender @ M^-1 @ S``를 적용하며,
    역변환은 ``M_blender = S @ M^-1 @ M_target @ M @ S^-1``를 적용한다.
    여기서 S는 ``meters_per_unit``로 이루어진 uniform scale 행렬이다.
    """

    def __init__(self, preset: str) -> None:
        if preset not in _PRESETS:
            raise ValueError(
                f"Unknown coordinate system preset: {preset}. "
                f"Available: {list(_PRESETS.keys())}"
            )

        self.preset = preset
        self._init_from_coordinate_system(_PRESETS[preset])

    @classmethod
    def from_coordinate_system(cls, cs: CoordinateSystem) -> "CoordinateConverter":
        """CoordinateSystem 객체로부터 변환기를 생성한다. (Importer용)"""
        instance = cls.__new__(cls)
        instance.preset = "CUSTOM"
        instance._init_from_coordinate_system(cs)
        return instance

    def _init_from_coordinate_system(self, cs: CoordinateSystem) -> None:
        self.target = cs
        self._validate_target()
        self._matrix_3x3 = self._build_conversion_matrix()
        self._matrix_4x4 = self._matrix_3x3.to_4x4()
        self._matrix_3x3_inv = self._matrix_3x3.inverted()
        self._matrix_4x4_inv = self._matrix_4x4.inverted()
        self._unit_scale = float(cs.meters_per_unit)

    def _validate_target(self) -> None:
        cs = self.target
        if cs.up_axis not in _AXIS_VECTORS:
            raise ValueError(f"Invalid up_axis: {cs.up_axis}")
        if cs.forward_axis not in _AXIS_VECTORS:
            raise ValueError(f"Invalid forward_axis: {cs.forward_axis}")
        if cs.handedness not in ("RIGHT", "LEFT"):
            raise ValueError(f"Invalid handedness: {cs.handedness}")
        if cs.winding not in ("CW", "CCW"):
            raise ValueError(f"Invalid winding: {cs.winding}")

        up = _AXIS_VECTORS[cs.up_axis]
        forward = _AXIS_VECTORS[cs.forward_axis]
        if abs(up.cross(forward).length) < 1e-6:
            raise ValueError(
                f"up_axis and forward_axis must not be parallel: "
                f"{cs.up_axis}, {cs.forward_axis}"
            )

        if cs.handedness != "RIGHT":
            raise ValueError(
                f"Only right-handed coordinate systems are supported, got {cs.handedness}"
            )

    def _build_conversion_matrix(self) -> Matrix:
        """Return M such that p_target = M @ p_blender (rotation/reflection only)."""
        cs = self.target
        up = _AXIS_VECTORS[cs.up_axis]
        forward = _AXIS_VECTORS[cs.forward_axis]
        # For a right-handed basis (right, forward, up):
        #   right x forward = up  =>  right = forward x up
        right = forward.cross(up)
        right.normalize()

        # B columns are target basis vectors expressed in Blender space.
        # p_blender = B @ p_target  =>  p_target = B^-1 @ p_blender = B^T @ p_blender.
        B = Matrix(
            (
                (right.x, forward.x, up.x),
                (right.y, forward.y, up.y),
                (right.z, forward.z, up.z),
            )
        )
        M = B.transposed()

        # 추가 방어: 실제로 right-handed basis인지 determinant로 확인
        if M.determinant() < 0:
            raise ValueError(
                f"Built conversion matrix is left-handed for up={cs.up_axis}, "
                f"forward={cs.forward_axis}"
            )

        return M

    def _scale_matrix(self, invert: bool = False) -> Matrix:
        """meters_per_unit에 따른 4x4 uniform scale 행렬을 반환한다."""
        scale = 1.0 / self._unit_scale if invert else self._unit_scale
        return Matrix.Scale(scale, 4)

    @property
    def winding(self) -> str:
        """target coordinate system의 winding을 반환한다."""
        return self.target.winding

    def convert_position(self, v: Vector) -> Vector:
        """Blender local/world position을 target local/world position으로 변환한다."""
        return (self._matrix_3x3 @ v) / self._unit_scale

    def convert_direction(self, v: Vector) -> Vector:
        """방향 벡터를 변환한다. (translation 없음, 단위 스케일 없음)"""
        return self._matrix_3x3 @ v

    def convert_matrix(self, m: Matrix) -> Matrix:
        """Blender 4x4 world matrix를 target 4x4 world matrix로 변환한다."""
        S_inv = self._scale_matrix(invert=True)
        S = self._scale_matrix()
        return S_inv @ self._matrix_4x4 @ m @ self._matrix_4x4_inv @ S

    def inverse_convert_position(self, v: Vector) -> Vector:
        """target local/world position을 Blender local/world position으로 변환한다."""
        return (self._matrix_3x3_inv @ v) * self._unit_scale

    def inverse_convert_direction(self, v: Vector) -> Vector:
        """target 방향 벡터를 Blender 방향 벡터로 변환한다. (translation 없음)"""
        return self._matrix_3x3_inv @ v

    def inverse_convert_matrix(self, m: Matrix) -> Matrix:
        """target 4x4 world matrix를 Blender 4x4 world matrix로 변환한다."""
        S = self._scale_matrix()
        S_inv = self._scale_matrix(invert=True)
        return S @ self._matrix_4x4_inv @ m @ self._matrix_4x4 @ S_inv
