from streamlit.testing.v1 import AppTest


def test_app_starts_with_secret_safe_provider_form(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))

    app = AppTest.from_file("src/pptmaker/ui/app.py")
    app.run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "PPT Maker"
    assert any(item.label == "API Key" for item in app.text_input)


def test_project_persists_but_api_key_does_not_survive_new_session(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    next(item for item in app.text_input if item.label == "项目名称").set_value(
        "Demo"
    )
    next(item for item in app.text_input if item.label == "API Key").set_value(
        "TEST_KEY"
    )
    next(item for item in app.button if item.label == "创建项目").click()
    app.run(timeout=10)

    reopened = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert next(
        item for item in reopened.text_input if item.label == "API Key"
    ).value == ""
    assert any(item.label == "当前项目" for item in reopened.selectbox)
    assert not reopened.exception
