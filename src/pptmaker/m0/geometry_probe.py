from pptmaker.evaluation.geometry import Box, out_of_bounds, overlap_ratio
from pptmaker.m0.contracts import ProbeResult, ProbeStatus


def run_geometry_probe() -> ProbeResult:
    checks = {
        "right_overflow": out_of_bounds(
            Box(90, 10, 20, 20), Box(0, 0, 100, 100)
        ),
        "half_overlap": overlap_ratio(
            Box(0, 0, 10, 10), Box(5, 0, 10, 10)
        )
        == 0.5,
        "touching_not_overlap": overlap_ratio(
            Box(0, 0, 10, 10), Box(10, 0, 10, 10)
        )
        == 0.0,
        "contained_overlap": overlap_ratio(
            Box(0, 0, 20, 20), Box(5, 5, 5, 5)
        )
        == 1.0,
    }
    return ProbeResult(
        name="geometry-checks",
        status=ProbeStatus.PASS if all(checks.values()) else ProbeStatus.FAIL,
        metrics={"checks": len(checks), "passed": sum(checks.values())},
        details={"checks": checks},
    )
