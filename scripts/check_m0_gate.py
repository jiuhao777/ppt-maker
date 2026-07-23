import json
from pathlib import Path

from pptmaker.m0.contracts import ProbeResult
from pptmaker.m0.evidence import POLICIES, ProbePolicy, source_fingerprint

REQUIRED = (
    "pptx-baseline",
    "powerpoint-worker",
    "geometry-checks",
    "upload-security",
    "deepseek-structured-output",
    "parser-core",
)


def check_gate(
    root: Path,
    required: tuple[str, ...] = REQUIRED,
    *,
    policies: dict[str, ProbePolicy] | None = None,
) -> list[str]:
    failures: list[str] = []
    active_policies = policies
    names = tuple(active_policies) if active_policies is not None else required
    for name in names:
        path = root / "artifacts" / "m0" / f"{name}.json"
        if not path.exists():
            failures.append(f"{name}: missing")
            continue
        try:
            payload = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{name}: invalid ({type(exc).__name__})")
            continue
        status = payload.get("status")
        if payload.get("name") not in (None, name):
            failures.append(f"{name}: evidence name mismatch")
        elif status != "pass":
            failures.append(f"{name}: {status or 'missing status'}")
        elif active_policies is not None:
            policy = active_policies[name]
            try:
                result = ProbeResult.model_validate(payload)
            except Exception as exc:
                failures.append(f"{name}: invalid schema ({type(exc).__name__})")
                continue
            if result.schema_version != 2:
                failures.append(f"{name}: legacy schema")
                continue
            if result.source_fingerprint != source_fingerprint(
                root, policy.source_paths
            ):
                failures.append(f"{name}: stale source fingerprint")
                continue
            python_version = result.environment.get("python", "")
            if not python_version.startswith(("3.10.", "3.11.", "3.12.")):
                failures.append(f"{name}: unsupported evidence environment")
                continue
            failed_metric = next(
                (
                    metric
                    for metric, check in policy.metric_checks.items()
                    if metric not in result.metrics
                    or not check(result.metrics[metric])
                ),
                None,
            )
            if failed_metric:
                failures.append(f"{name}: metric {failed_metric} failed")
                continue
            if policy.require_evidence:
                if not result.evidence:
                    failures.append(f"{name}: evidence missing")
                    continue
                root_resolved = root.resolve()
                invalid_evidence = False
                for value in result.evidence:
                    evidence = Path(value)
                    if not evidence.is_absolute():
                        evidence = root / evidence
                    try:
                        evidence.resolve().relative_to(root_resolved)
                    except ValueError:
                        invalid_evidence = True
                        break
                    if not evidence.exists():
                        invalid_evidence = True
                        break
                if invalid_evidence:
                    failures.append(f"{name}: evidence path invalid")
    return failures


def main() -> int:
    errors = check_gate(Path.cwd(), policies=POLICIES)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"M0 gate passed: {len(REQUIRED)} mandatory probes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
