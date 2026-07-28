from streamlit.testing.v1 import AppTest


def test_app_starts_with_secret_safe_provider_form(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))

    app = AppTest.from_file("src/pptmaker/ui/app.py")
    app.run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "PPT Maker"
    assert any(item.label == "API Key" for item in app.text_input)
    assert any(
        item.label == "博查 API Key（可选）" for item in app.text_input
    )
    assert any(item.label == "测试搜索连接" for item in app.button)


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
    assert next(
        item
        for item in reopened.text_input
        if item.label == "博查 API Key（可选）"
    ).value == ""
    assert any(item.label == "当前项目" for item in reopened.selectbox)
    assert not reopened.exception


def test_confirmed_delete_clears_selected_project(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    next(item for item in app.text_input if item.label == "项目名称").set_value(
        "Delete me"
    )
    next(item for item in app.button if item.label == "创建项目").click()
    app.run(timeout=10)
    next(
        item for item in app.checkbox if item.label == "确认删除此项目"
    ).check()
    app.run(timeout=10)

    next(item for item in app.button if item.label == "删除项目").click()
    app.run(timeout=10)

    assert not app.exception
    assert not any(item.label == "当前项目" for item in app.selectbox)


def test_duplicate_project_name_shows_warning(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    for _ in range(2):
        next(
            item for item in app.text_input if item.label == "项目名称"
        ).set_value("Demo")
        next(item for item in app.button if item.label == "创建项目").click()
        app.run(timeout=10)

    assert not app.exception
    assert any("已存在" in item.value for item in app.warning)


def test_new_project_shows_next_action(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    next(item for item in app.text_input if item.label == "项目名称").set_value(
        "Guided"
    )
    next(item for item in app.button if item.label == "创建项目").click()
    app.run(timeout=10)

    assert any("需求分析" in item.value for item in app.info)
