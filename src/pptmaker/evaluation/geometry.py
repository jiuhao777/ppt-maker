from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("box dimensions must be non-negative")


def out_of_bounds(box: Box, canvas: Box) -> bool:
    return (
        box.x < canvas.x
        or box.y < canvas.y
        or box.x + box.width > canvas.x + canvas.width
        or box.y + box.height > canvas.y + canvas.height
    )


def overlap_ratio(left: Box, right: Box) -> float:
    width = max(
        0,
        min(left.x + left.width, right.x + right.width) - max(left.x, right.x),
    )
    height = max(
        0,
        min(left.y + left.height, right.y + right.height) - max(left.y, right.y),
    )
    intersection = width * height
    denominator = min(left.width * left.height, right.width * right.height)
    return 0.0 if denominator == 0 else intersection / denominator
