from pptmaker.m0.vision_metrics import score_labels


def test_scores_true_false_positive_and_false_negative():
    score = score_labels(
        expected={"overflow", "crowded"},
        predicted={"overflow", "irrelevant_image"},
    )
    assert score.true_positive == 1
    assert score.false_positive == 1
    assert score.false_negative == 1
    assert score.precision == 0.5
    assert score.recall == 0.5
    assert score.f1 == 0.5


def test_empty_expected_and_prediction_is_perfect():
    score = score_labels(expected=set(), predicted=set())
    assert score.precision == score.recall == score.f1 == 1.0
