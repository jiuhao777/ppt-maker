import os

import pytest

from pptmaker.providers import PRESETS, provider_for


@pytest.mark.online
def test_deepseek_capability_probe():
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        pytest.skip("DEEPSEEK_API_KEY is not configured")

    report = provider_for(PRESETS["deepseek"]).probe(key)

    assert report.status == "success"
    assert report.capabilities["structured_output"].value is True
