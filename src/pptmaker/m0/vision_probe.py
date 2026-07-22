import importlib.util
import json
from pathlib import Path


VRAM_BUDGET_BYTES = 6_500 * 1024 * 1024


def inspect_candidate(repository_root: Path) -> dict:
    model = repository_root / "models" / "QwenQwen3-VL-4B-Instruct"
    weights = sorted(model.glob("*.safetensors"))
    weight_bytes = sum(path.stat().st_size for path in weights)
    quantization_available = all(
        importlib.util.find_spec(package) is not None
        for package in ("accelerate", "bitsandbytes")
    )
    reasons: list[str] = []
    if weight_bytes > VRAM_BUDGET_BYTES and not quantization_available:
        reasons.append(
            "BF16 weights exceed the 6.5 GiB safety budget and the approved 4-bit runtime is unavailable."
        )
    reasons.append(
        "Only five synthetic harness cases exist; admission requires at least 20 real PowerPoint-rendered pages."
    )
    return {
        "candidate": "Qwen3-VL-4B-Instruct",
        "path_exists": model.is_dir(),
        "weight_bytes": weight_bytes,
        "vram_budget_bytes": VRAM_BUDGET_BYTES,
        "quantization_runtime_available": quantization_available,
        "load_attempted": False,
        "admitted": False,
        "reasons": reasons,
    }


def main() -> int:
    root = Path.cwd()
    result = inspect_candidate(root)
    output = root / "artifacts" / "m0" / "vision-model-resource.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
