"""Topolyx 전체에서 공유하는 작은 유틸리티."""

from typing import List, Sequence

from mathutils import Matrix


def matrix_to_column_major_list(matrix: Matrix) -> List[float]:
    """mathutils.Matrix를 column-major 16개 float list로 변환한다.

    Blender Python API의 ``matrix[row][col]`` 접근은 row-major 표기이므로,
    column-major 직렬화를 위해 col을 바깥 루프로 순회한다.
    """
    return [matrix[row][col] for col in range(4) for row in range(4)]


def column_major_list_to_matrix(values: Sequence[float]) -> Matrix:
    """column-major 16개 float list를 mathutils.Matrix로 변환한다."""
    if len(values) != 16:
        raise ValueError(f"Expected 16 values, got {len(values)}")

    # values[col * 4 + row] = matrix[row][col]
    rows = [
        [values[col * 4 + row] for col in range(4)]
        for row in range(4)
    ]
    return Matrix(rows)
