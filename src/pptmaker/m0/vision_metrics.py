from dataclasses import dataclass


@dataclass(frozen=True)
class LabelScore:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float


def score_labels(expected: set[str], predicted: set[str]) -> LabelScore:
    true_positive = len(expected & predicted)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 1.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return LabelScore(
        true_positive,
        false_positive,
        false_negative,
        precision,
        recall,
        f1,
    )
