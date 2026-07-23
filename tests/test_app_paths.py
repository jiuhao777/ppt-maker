from pptmaker.app_paths import database_path


def test_database_path_uses_injected_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))

    assert database_path() == tmp_path / "pptmaker.db"
