import pytest

from pptmaker.evaluation.geometry import Box, out_of_bounds, overlap_ratio


def test_detects_right_overflow():
    assert out_of_bounds(Box(90, 10, 20, 20), Box(0, 0, 100, 100))


def test_box_exactly_on_canvas_is_in_bounds():
    assert not out_of_bounds(Box(10, 20, 100, 50), Box(10, 20, 100, 50))


def test_detects_left_and_top_overflow_on_offset_canvas():
    canvas = Box(10, 10, 100, 100)
    assert out_of_bounds(Box(9, 10, 10, 10), canvas)
    assert out_of_bounds(Box(10, 9, 10, 10), canvas)


def test_overlap_ratio_uses_smaller_box_area():
    assert overlap_ratio(Box(0, 0, 10, 10), Box(5, 0, 10, 10)) == 0.5


def test_overlap_ratio_is_symmetric():
    left = Box(0, 0, 20, 20)
    right = Box(10, 10, 10, 10)
    assert overlap_ratio(left, right) == overlap_ratio(right, left) == 1.0


def test_touching_edges_do_not_overlap():
    assert overlap_ratio(Box(0, 0, 10, 10), Box(10, 0, 10, 10)) == 0.0


def test_zero_area_box_has_zero_overlap():
    assert overlap_ratio(Box(0, 0, 0, 10), Box(0, 0, 10, 10)) == 0.0


def test_negative_dimensions_are_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        Box(0, 0, -1, 10)
