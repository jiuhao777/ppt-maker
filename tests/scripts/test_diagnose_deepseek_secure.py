from scripts.diagnose_deepseek_secure import _redact


def test_diagnostic_output_redacts_secrets():
    value = _redact(
        "Authorization: Bearer sk-secret api_key=sk-second"
    )
    assert "sk-secret" not in value
    assert "sk-second" not in value
