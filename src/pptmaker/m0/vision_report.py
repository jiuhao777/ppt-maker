from statistics import median


def summarize(records: list[dict]) -> dict[str, float | int]:
    true_positive = false_positive = false_negative = 0
    latencies: list[float] = []
    peaks: list[int] = []
    for record in records:
        expected = set(record["expected"])
        predicted = set(record["predicted"])
        true_positive += len(expected & predicted)
        false_positive += len(predicted - expected)
        false_negative += len(expected - predicted)
        latencies.append(float(record["latency_seconds"]))
        peaks.append(int(record["peak_vram_bytes"]))
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
    ordered = sorted(latencies)
    p95_index = max(0, int(len(ordered) * 0.95 + 0.999999) - 1)
    return {
        "cases": len(records),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": false_positive / max(len(records), 1),
        "json_valid_rate": sum(bool(row["json_valid"]) for row in records)
        / max(len(records), 1),
        "p50_seconds": median(latencies) if latencies else 0.0,
        "p95_seconds": ordered[p95_index] if ordered else 0.0,
        "peak_vram_bytes": max(peaks, default=0),
    }
