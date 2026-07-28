import hashlib
import os
import re
import tempfile
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

from pptmaker.assets.models import AssetRecord
from pptmaker.security.fetcher import (
    Resolver,
    SafeFetchPolicy,
    safe_fetch_result,
)


class InvalidImage(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedImage:
    path: Path
    content_hash: str
    mime_type: str
    byte_size: int
    width: int
    height: int


_FORMATS = {
    "image/png": ("PNG", ".png"),
    "image/jpeg": ("JPEG", ".jpg"),
    "image/webp": ("WEBP", ".webp"),
}


def download_image(
    candidate: AssetRecord,
    destination_dir: Path,
    resolver: Resolver,
    *,
    transport: httpx.BaseTransport | None = None,
) -> VerifiedImage:
    policy = SafeFetchPolicy(
        allowed_content_types=tuple(_FORMATS),
        max_response_bytes=10 * 1024 * 1024,
    )
    result = None
    last_error = None
    for url in dict.fromkeys(
        [str(candidate.original_url), str(candidate.thumbnail_url)]
    ):
        try:
            result = safe_fetch_result(
                url, resolver, policy, transport
            )
            break
        except Exception as exc:
            last_error = exc
    if result is None:
        raise last_error
    expected_format, suffix = _FORMATS[result.content_type]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(result.content)) as image:
                actual_format = image.format
                width, height = image.size
                image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidImage("image decode failed") from exc
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage("image dimensions are unsafe") from exc
    if actual_format != expected_format:
        raise InvalidImage("image format does not match MIME")
    if width < 320 or height < 180 or width > 12_000 or height > 12_000:
        raise InvalidImage("image dimensions are outside limits")

    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", candidate.id)[:100]
    final_path = destination / f"{safe_id}{suffix}"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{safe_id}-",
        suffix=".tmp",
        dir=destination,
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(result.content)
        os.replace(temporary_name, final_path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return VerifiedImage(
        path=final_path,
        content_hash=hashlib.sha256(result.content).hexdigest(),
        mime_type=result.content_type,
        byte_size=len(result.content),
        width=width,
        height=height,
    )
