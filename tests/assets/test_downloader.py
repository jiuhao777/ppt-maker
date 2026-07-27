from io import BytesIO

import httpx
import pytest
from PIL import Image

from pptmaker.assets.downloader import InvalidImage, download_image
from tests.assets.test_models import record
from tests.security.test_fetcher import public_resolver


def image_bytes(format_name="PNG", size=(640, 360)):
    output = BytesIO()
    Image.new("RGB", size, "blue").save(output, format=format_name)
    return output.getvalue()


def transport_for(content, mime):
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=content,
            headers={"Content-Type": mime},
            request=request,
        )
    )


def test_download_verifies_image_and_publishes_hash(tmp_path):
    verified = download_image(
        record(),
        tmp_path,
        public_resolver,
        transport=transport_for(image_bytes(), "image/png"),
    )

    assert verified.path.exists()
    assert verified.mime_type == "image/png"
    assert verified.width == 640
    assert len(verified.content_hash) == 64


def test_download_rejects_mime_and_decoded_format_mismatch(tmp_path):
    with pytest.raises(InvalidImage, match="format"):
        download_image(
            record(),
            tmp_path,
            public_resolver,
            transport=transport_for(image_bytes("JPEG"), "image/png"),
        )
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_truncated_image_without_partial_file(tmp_path):
    with pytest.raises(InvalidImage, match="decode"):
        download_image(
            record(),
            tmp_path,
            public_resolver,
            transport=transport_for(b"not-an-image", "image/png"),
        )
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_dimensions_outside_policy(tmp_path):
    with pytest.raises(InvalidImage, match="dimensions"):
        download_image(
            record(),
            tmp_path,
            public_resolver,
            transport=transport_for(
                image_bytes(size=(100, 100)), "image/png"
            ),
        )


def test_download_revalidates_private_redirect(tmp_path):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1/private.png"},
            request=request,
        )
    )
    with pytest.raises(ValueError, match="forbidden"):
        download_image(
            record(),
            tmp_path,
            public_resolver,
            transport=transport,
        )
    assert list(tmp_path.iterdir()) == []
