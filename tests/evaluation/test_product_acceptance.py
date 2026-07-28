from pptmaker.evaluation.product_acceptance import evaluate_deck
from pptmaker.m3.blueprint_compiler import compile_blueprint, design_from_blueprint
from pptmaker.m3.builder import build_pptx
from tests.acceptance.fixtures import acceptance_inputs


def test_acceptance_report_exposes_approved_thresholds(tmp_path):
    blueprint, facts, assets = acceptance_inputs(tmp_path)
    design = design_from_blueprint(blueprint)
    specs = compile_blueprint(blueprint, facts, assets, design)
    output = build_pptx(specs, design, tmp_path / "metrics.pptx")

    report = evaluate_deck(blueprint, specs, output)
    if artifact_dir := os.getenv("PPTMAKER_P4_ARTIFACT_DIR"):
        target = Path(artifact_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "metrics.json").write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )

    assert report.requirement_coverage >= 0.90
    assert report.title_conclusion_rate >= 0.90
    assert report.severe_geometry_defects == 0
    assert report.density_violation_rate <= 0.05
    assert report.public_fact_traceability >= 0.95
    assert report.asset_download_safety_rate == 1.0
import os
from pathlib import Path
