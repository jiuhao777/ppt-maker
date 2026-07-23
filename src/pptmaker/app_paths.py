import os
from pathlib import Path


def application_data_dir() -> Path:
    override = os.getenv("PPTMAKER_DATA_DIR")
    root = Path(override) if override else Path(os.environ["LOCALAPPDATA"]) / "PPTMaker"
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return application_data_dir() / "pptmaker.db"
