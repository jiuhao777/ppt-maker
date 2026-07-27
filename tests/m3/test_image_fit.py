import pytest

from pptmaker.m3.image_fit import crop_to_fill


def test_wide_image_crops_left_and_right():
    left, top, right, bottom = crop_to_fill(1600, 800, 4, 3)
    assert left == pytest.approx(right)
    assert left > 0
    assert top == bottom == 0


def test_tall_image_crops_top_and_bottom():
    left, top, right, bottom = crop_to_fill(800, 1600, 4, 3)
    assert top == pytest.approx(bottom)
    assert top > 0
    assert left == right == 0


def test_invalid_dimensions_are_rejected():
    with pytest.raises(ValueError):
        crop_to_fill(0, 100, 4, 3)
