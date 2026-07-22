from pathlib import Path
from zipfile import ZipFile

import httpx

from pptmaker.m0.contracts import ProbeResult, ProbeStatus
from pptmaker.security.fetcher import (
    SafeFetchPolicy,
    UnsafeUrl,
    safe_fetch,
    validate_target,
)
from pptmaker.security.uploads import (
    ArchiveLimits,
    UnsafeArchive,
    inspect_office_package,
    inspect_zip,
)


def _must_reject(operation, exception_type: type[Exception]) -> bool:
    try:
        operation()
    except exception_type:
        return True
    return False


def run_security_probe(root: Path) -> ProbeResult:
    work = root / "artifacts" / "m0" / "security-probe"
    work.mkdir(parents=True, exist_ok=True)

    traversal = work / "traversal.zip"
    with ZipFile(traversal, "w") as archive:
        archive.writestr("../escape.txt", "x")

    macro = work / "macro.pptx"
    with ZipFile(macro, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/presentation.xml", "<p/>")
        archive.writestr("ppt/vbaProject.bin", "macro")

    public_ip = "93.184.216.34"
    redirect_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"Location": "http://169.254.169.254/latest/meta-data/"},
            request=request,
        )
    )
    executable_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"binary",
            headers={"Content-Type": "application/x-msdownload"},
            request=request,
        )
    )

    rebinding_answers = iter([[public_ip], ["127.0.0.1"]])
    checks = {
        "zip_path_traversal": _must_reject(
            lambda: inspect_zip(traversal, ArchiveLimits()), UnsafeArchive
        ),
        "office_macro": _must_reject(
            lambda: inspect_office_package(macro, ArchiveLimits()), UnsafeArchive
        ),
        "cloud_metadata": _must_reject(
            lambda: validate_target(
                "http://169.254.169.254/latest/meta-data/",
                lambda host: [host],
                SafeFetchPolicy(),
            ),
            UnsafeUrl,
        ),
        "dns_rebinding": _must_reject(
            lambda: validate_target(
                "https://example.com/",
                lambda _host: next(rebinding_answers),
                SafeFetchPolicy(),
            ),
            UnsafeUrl,
        ),
        "redirect_revalidation": _must_reject(
            lambda: safe_fetch(
                "https://example.com/",
                lambda _host: [public_ip],
                SafeFetchPolicy(),
                redirect_transport,
            ),
            UnsafeUrl,
        ),
        "response_mime": _must_reject(
            lambda: safe_fetch(
                "https://example.com/file.exe",
                lambda _host: [public_ip],
                SafeFetchPolicy(),
                executable_transport,
            ),
            UnsafeUrl,
        ),
    }
    passed = all(checks.values())
    return ProbeResult(
        name="upload-security",
        status=ProbeStatus.PASS if passed else ProbeStatus.FAIL,
        metrics={
            "challenge_checks": len(checks),
            "passed_checks": sum(checks.values()),
        },
        limitations=[
            "M5 must pin the validated IP to the socket connection to close DNS TOCTOU.",
            "Fetched content remains untrusted and must be normalized before entering Fact Store.",
            "Asset license metadata and image dimensions are enforced by the later material ingestion boundary.",
        ],
        details={"checks": checks},
    )
