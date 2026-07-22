from pathlib import Path

from pptmaker.m0.vision_probe import VRAM_BUDGET_BYTES, inspect_candidate


def test_oversized_unquantized_candidate_is_not_admitted(tmp_path: Path):
    model = tmp_path / "models" / "QwenQwen3-VL-4B-Instruct"
    model.mkdir(parents=True)
    weight = model / "model.safetensors"
    with weight.open("wb") as stream:
        stream.truncate(VRAM_BUDGET_BYTES + 1)

    result = inspect_candidate(tmp_path)

    assert result["admitted"] is False
    assert result["load_attempted"] is False
    assert result["weight_bytes"] > VRAM_BUDGET_BYTES
