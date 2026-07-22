import json
import time
from pathlib import Path

from pptmaker.m0.vision_adapter import VisionAdapter
from pptmaker.m0.vision_schema import VisionReview


PROMPT = """检查这张中文 PPT 页面。只输出 JSON，不要输出 Markdown。
JSON 必须包含 slide_id（字符串）、issues（数组）和 overall_score（0-100 整数）。
问题类型只能是 overflow、crowded、weak_hierarchy、irrelevant_image、misalignment、
inconsistent_style。每个问题必须包含 type、severity、region、evidence、suggestion、
confidence。没有问题时 issues 为空数组。"""


def parse_review(raw: str) -> VisionReview:
    cleaned = raw.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return VisionReview.model_validate_json(cleaned)


def _cuda_peak_reader():
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            return torch.cuda.max_memory_allocated
    except Exception:
        pass
    return lambda: 0


def run_manifest(
    adapter: VisionAdapter,
    manifest: Path,
    *,
    repository_root: Path | None = None,
    measure_cuda: bool = False,
) -> list[dict]:
    root = repository_root or Path.cwd()
    records: list[dict] = []
    for line in manifest.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        image = Path(case["image"])
        if not image.is_absolute():
            image = root / image
        read_peak = _cuda_peak_reader() if measure_cuda else (lambda: 0)
        started = time.perf_counter()
        raw = ""
        try:
            raw = adapter.review(image, PROMPT)
            review = parse_review(raw)
            predicted = sorted({issue.type for issue in review.issues})
            valid, error = True, None
        except Exception as exc:
            predicted, valid = [], False
            error = f"{type(exc).__name__}: {exc}"
        records.append(
            {
                "model_id": adapter.model_id,
                "case_id": case["case_id"],
                "split": case["split"],
                "expected": case["expected"],
                "predicted": predicted,
                "json_valid": valid,
                "error": error,
                "raw": raw,
                "latency_seconds": time.perf_counter() - started,
                "peak_vram_bytes": int(read_peak()),
            }
        )
    return records
