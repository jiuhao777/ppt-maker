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
    observed_targets = []

    class SafeResponse:
        status_code = 200
        is_redirect = False
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"png"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class RecordingConnector:
        def request(self, target, method="GET", headers=None):
            observed_targets.append(target)
            return SafeResponse()

    safe_fetch(
        "https://example.com/image.png",
        lambda _host: [public_ip],
        SafeFetchPolicy(),
        connector=RecordingConnector(),
    )
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
        "connection_uses_validated_ip": (
            len(observed_targets) == 1
            and observed_targets[0].addresses == (public_ip,)
        ),
        "https_preserves_original_hostname": (
            len(observed_targets) == 1
            and observed_targets[0].scheme == "https"
            and observed_targets[0].hostname == "example.com"
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
            "Fetched content remains untrusted and must be normalized before entering Fact Store.",
            "Asset license metadata and image dimensions are enforced by the later material ingestion boundary.",
        ],
        details={"checks": checks},
    )
