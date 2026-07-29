"""Blender 좌표계와 Topolyx v1.0.0 고정 좌표계 사이를 변환하는 유틸리티.

Topolyx v1.0.0은 좌표계를 +Z up, +Y forward, right-handed, CCW winding으로 고정한다.
따라서 본 변환기는 meters_per_unit에 따른 위치/행렬 스케일만 수행한다.
"""

import math
from typing import Union

from mathutils import Matrix, Quaternion, Vector

from .topolyx_types import CoordinateSystem


class CoordinateConverter:
    """Blender 좌표계와 Topolyx v1.0.0 고정 좌표계 사이를 변환한다.

    v1.0.0에서 축과 winding은 Blender와 동일하므로, 유일한 변환은
    ``meters_per_unit``에 따른 위치/행렬 스케일이다.
    """

    def __init__(self, preset_or_cs: Union[str, CoordinateSystem]) -> None:
        if isinstance(preset_or_cs, CoordinateSystem):
            self.target = preset_or_cs
        elif isinstance(preset_or_cs, str):
            # Blender와 Topolyx v1.0.0 고정 좌표계는 동일하다.
            if preset_or_cs not in {"BLENDER", "TOPOLYX_DEFAULT"}:
                raise ValueError(
                    f"Unknown CoordinateConverter preset: {preset_or_cs!r}"
                )
            self.target = CoordinateSystem()
        else:
            raise TypeError(
                f"CoordinateConverter expects CoordinateSystem or str, got {type(preset_or_cs)}"
            )
        self._validate_target()
        self._unit_scale = float(self.target.meters_per_unit)

    @classmethod
    def from_coordinate_system(cls, cs: CoordinateSystem) -> "CoordinateConverter":
        """CoordinateSystem 객체로부터 변환기를 생성한다. (Importer용)"""
        return cls(cs)

    def _validate_target(self) -> None:
        """Topolyx v1.0.0 고정 좌표계 조건을 검증한다."""
        cs = self.target
        if cs.up_axis != "+Z":
            raise ValueError(f"Topolyx v1.0.0 requires up_axis=+Z, got {cs.up_axis!r}")
        if cs.forward_axis != "+Y":
            raise ValueError(
                f"Topolyx v1.0.0 requires forward_axis=+Y, got {cs.forward_axis!r}"
            )
        if cs.handedness != "RIGHT":
            raise ValueError(
                f"Topolyx v1.0.0 requires right-handedness, got {cs.handedness!r}"
            )
        if cs.winding != "CCW":
            raise ValueError(
                f"Topolyx v1.0.0 requires CCW winding, got {cs.winding!r}"
            )
        if (
            not isinstance(cs.meters_per_unit, (int, float))
            or not math.isfinite(cs.meters_per_unit)
            or cs.meters_per_unit <= 0
        ):
            raise ValueError(
                f"meters_per_unit must be a positive finite number, got {cs.meters_per_unit!r}"
            )

    @property
    def winding(self) -> str:
        """target coordinate system의 winding을 반환한다."""
        return "CCW"

    def _scale_matrix(self, invert: bool = False) -> Matrix:
        """meters_per_unit에 따른 4x4 uniform scale 행렬을 반환한다."""
        scale = 1.0 / self._unit_scale if invert else self._unit_scale
        return Matrix.Scale(scale, 4)

    def convert_position(self, v: Vector) -> Vector:
        """Blender local/world position을 target local/world position으로 변환한다."""
        return v / self._unit_scale

    def convert_direction(self, v: Vector) -> Vector:
        """방향 벡터를 변환한다. (translation 없음, 단위 스케일 없음)"""
        return v

    def convert_normal(self, v: Vector) -> Vector:
        """법선 벡터를 변환하고 단위 벡터로 재정규화한다."""
        n = Vector(v)
        n.normalize()
        return n

    def convert_matrix(self, m: Matrix) -> Matrix:
        """Blender 4x4 world matrix를 target 4x4 world matrix로 변환한다.

        회전/방향 축은 Blender와 Topolyx 1.0.0이 동일하므로, meters_per_unit에 따른
        uniform scale만 적용한다: ``M_target = S^-1 @ M @ S``.
        """
        S_inv = self._scale_matrix(invert=True)
        S = self._scale_matrix()
        return S_inv @ m @ S

    def convert_rotation(self, q: Quaternion) -> Quaternion:
        """Blender 쿼터니언 회전을 target 좌표계 쿼터니언으로 변환한다."""
        return q

    def convert_tangent(self, t: Vector) -> Vector:
        """Tangent 벡터 (x, y, z, w)를 target 좌표계로 변환한다."""
        xyz = Vector((t.x, t.y, t.z))
        xyz.normalize()
        return Vector((xyz.x, xyz.y, xyz.z, t.w))

    def inverse_convert_position(self, v: Vector) -> Vector:
        """target local/world position을 Blender local/world position으로 변환한다."""
        return v * self._unit_scale

    def inverse_convert_direction(self, v: Vector) -> Vector:
        """target 방향 벡터를 Blender 방향 벡터로 변환한다. (translation 없음)"""
        return v

    def inverse_convert_normal(self, v: Vector) -> Vector:
        """target 법선 벡터를 Blender 좌표계로 변환하고 단위 벡터로 재정규화한다."""
        n = Vector(v)
        n.normalize()
        return n

    def inverse_convert_matrix(self, m: Matrix) -> Matrix:
        """target 4x4 world matrix를 Blender 4x4 world matrix로 변환한다.

        회전/방향 축은 Blender와 Topolyx 1.0.0이 동일하므로, meters_per_unit에 따른
        uniform scale만 적용한다: ``M_blender = S @ M @ S^-1``.
        """
        S = self._scale_matrix()
        S_inv = self._scale_matrix(invert=True)
        return S @ m @ S_inv

    def inverse_convert_rotation(self, q: Quaternion) -> Quaternion:
        """target 쿼터니언 회전을 Blender 좌표계 쿼터니언으로 변환한다."""
        return q

    def inverse_convert_tangent(self, t: Vector) -> Vector:
        """target Tangent 벡터 (x, y, z, w)를 Blender 좌표계로 변환한다."""
        xyz = Vector((t.x, t.y, t.z))
        xyz.normalize()
        return Vector((xyz.x, xyz.y, xyz.z, t.w))
