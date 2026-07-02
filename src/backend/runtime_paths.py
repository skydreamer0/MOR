from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "MOR"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return project_root()


def default_data_root() -> Path:
    if not getattr(sys, "frozen", False):
        return project_root()

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    for env_name in ("LOCALAPPDATA", "APPDATA"):
        raw = os.environ.get(env_name)
        if raw:
            return Path(raw) / APP_NAME

    if sys.platform.startswith("win"):
        return Path.home() / "AppData" / "Local" / APP_NAME

    return Path.home() / ".local" / "share" / APP_NAME
