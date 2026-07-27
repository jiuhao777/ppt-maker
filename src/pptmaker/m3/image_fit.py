def crop_to_fill(
    source_width: int,
    source_height: int,
    target_width: float,
    target_height: float,
) -> tuple[float, float, float, float]:
    if min(source_width, source_height, target_width, target_height) <= 0:
        raise ValueError("image and target dimensions must be positive")
    source_ratio = source_width / source_height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        visible = target_ratio / source_ratio
        crop = (1 - visible) / 2
        return crop, 0.0, crop, 0.0
    visible = source_ratio / target_ratio
    crop = (1 - visible) / 2
    return 0.0, crop, 0.0, crop
