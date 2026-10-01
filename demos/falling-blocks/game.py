"""Dependency-free falling-blocks environment used by the public demo."""

from __future__ import annotations

from dataclasses import dataclass

WIDTH = 10
HEIGHT = 20

_SHAPES = {
    "I": (
        ((0, 0), (1, 0), (2, 0), (3, 0)),
        ((0, 0), (0, 1), (0, 2), (0, 3)),
    ),
    "O": (((0, 0), (1, 0), (0, 1), (1, 1)),),
    "T": (
        ((0, 0), (1, 0), (2, 0), (1, 1)),
        ((1, 0), (0, 1), (1, 1), (1, 2)),
        ((1, 0), (0, 1), (1, 1), (2, 1)),
        ((0, 0), (0, 1), (1, 1), (0, 2)),
    ),
    "S": (
        ((1, 0), (2, 0), (0, 1), (1, 1)),
        ((0, 0), (0, 1), (1, 1), (1, 2)),
    ),
    "Z": (
        ((0, 0), (1, 0), (1, 1), (2, 1)),
        ((1, 0), (0, 1), (1, 1), (0, 2)),
    ),
    "J": (
        ((0, 0), (0, 1), (1, 1), (2, 1)),
        ((0, 0), (1, 0), (0, 1), (0, 2)),
        ((0, 0), (1, 0), (2, 0), (2, 1)),
        ((1, 0), (1, 1), (0, 2), (1, 2)),
    ),
    "L": (
        ((2, 0), (0, 1), (1, 1), (2, 1)),
        ((0, 0), (0, 1), (0, 2), (1, 2)),
        ((0, 0), (1, 0), (2, 0), (0, 1)),
        ((0, 0), (1, 0), (1, 1), (1, 2)),
    ),
}

PIECES = tuple(_SHAPES)


@dataclass(frozen=True)
class Placement:
    rotation: int
    column: int
    landing_row: int
    board: tuple[tuple[int, ...], ...]
    lines_cleared: int
    features: dict[str, int | list[int]]

    @property
    def choice_id(self) -> str:
        return f"r{self.rotation}x{self.column}"

    @property
    def description(self) -> str:
        return (
            f"rotation {self.rotation}, column {self.column}; "
            f"clears {self.lines_cleared}; holes {self.features['holes']}; "
            f"max height {self.features['max_height']}; "
            f"roughness {self.features['roughness']}"
        )


def empty_board() -> list[list[int]]:
    return [[0] * WIDTH for _ in range(HEIGHT)]


def shape(piece: str, rotation: int) -> tuple[tuple[int, int], ...]:
    return _SHAPES[piece][rotation]


def shape_size(cells: tuple[tuple[int, int], ...]) -> tuple[int, int]:
    return max(x for x, _ in cells) + 1, max(y for _, y in cells) + 1


def collides(board: list[list[int]], cells, column: int, row: int) -> bool:
    for dx, dy in cells:
        x, y = column + dx, row + dy
        if x < 0 or x >= WIDTH or y >= HEIGHT:
            return True
        if y >= 0 and board[y][x]:
            return True
    return False


def landing_row(board: list[list[int]], cells, column: int) -> int | None:
    width, height = shape_size(cells)
    if column < 0 or column + width > WIDTH:
        return None
    last = None
    for row in range(-height + 1, HEIGHT - height + 1):
        if collides(board, cells, column, row):
            return last
        last = row
    return last


def apply(board: list[list[int]], cells, column: int, row: int):
    result = [line[:] for line in board]
    for dx, dy in cells:
        x, y = column + dx, row + dy
        if y < 0:
            raise ValueError("placement stacks above the board")
        result[y][x] = 1
    kept = [line for line in result if not all(line)]
    cleared = HEIGHT - len(kept)
    return [[0] * WIDTH for _ in range(cleared)] + kept, cleared


def board_features(board: list[list[int]]) -> dict[str, int | list[int]]:
    heights = []
    holes = 0
    for column in range(WIDTH):
        top = next((row for row in range(HEIGHT) if board[row][column]), None)
        heights.append(0 if top is None else HEIGHT - top)
        if top is not None:
            holes += sum(not board[row][column] for row in range(top + 1, HEIGHT))
    roughness = sum(abs(a - b) for a, b in zip(heights, heights[1:]))
    return {
        "column_heights": heights,
        "aggregate_height": sum(heights),
        "holes": holes,
        "roughness": roughness,
        "max_height": max(heights),
    }


def legal_placements(board: list[list[int]], piece: str) -> list[Placement]:
    placements = []
    for rotation, cells in enumerate(_SHAPES[piece]):
        width, _ = shape_size(cells)
        for column in range(WIDTH - width + 1):
            row = landing_row(board, cells, column)
            if row is None or row < 0:
                continue
            after, cleared = apply(board, cells, column, row)
            placements.append(Placement(
                rotation, column, row,
                tuple(tuple(value for value in line) for line in after),
                cleared, board_features(after),
            ))
    return placements


def shortlist(placements: list[Placement], limit: int = 8) -> list[Placement]:
    """Deterministic safety prefilter; Spark makes the final choice."""
    return sorted(placements, key=lambda p: (
        -p.lines_cleared,
        p.features["holes"],
        p.features["max_height"],
        p.features["roughness"],
        p.features["aggregate_height"],
        p.rotation,
        p.column,
    ))[:limit]


def rows(board: list[list[int]]) -> list[str]:
    return ["".join("#" if value else "." for value in line) for line in board]
