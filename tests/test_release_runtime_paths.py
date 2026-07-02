from __future__ import annotations

from pathlib import Path

from src.backend import runtime_paths
from src.backend.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_resource_root_uses_pyinstaller_bundle_when_frozen(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_paths.sys, "_MEIPASS", str(bundle_root), raising=False)

    assert runtime_paths.resource_root() == bundle_root.resolve()


def test_default_data_root_uses_appdata_when_frozen(monkeypatch, tmp_path):
    appdata_root = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("LOCALAPPDATA", str(appdata_root))
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32", raising=False)
    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)

    assert runtime_paths.default_data_root() == appdata_root / "MOR"


def test_default_data_root_uses_application_support_on_macos(monkeypatch, tmp_path):
    home_root = tmp_path / "Users" / "tester"
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin", raising=False)
    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_paths.Path, "home", staticmethod(lambda: home_root))

    assert runtime_paths.default_data_root() == home_root / "Library" / "Application Support" / "MOR"


def test_create_app_initializes_the_database_in_user_data_when_frozen(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    appdata_root = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("LOCALAPPDATA", str(appdata_root))
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32", raising=False)
    monkeypatch.setattr(runtime_paths, "resource_root", lambda: bundle_root)
    monkeypatch.setattr(runtime_paths, "default_data_root", lambda: appdata_root / "MOR")

    app = create_app({"TESTING": True})

    assert app is not None
    assert (appdata_root / "MOR" / "mor_workbench.db").exists()


def test_create_app_respects_db_base_override(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_paths, "resource_root", lambda: PROJECT_ROOT)
    db_base = tmp_path / "custom-db"

    app = create_app({"TESTING": True, "DB_BASE_PATH": db_base, "DATA_BASE_PATH": db_base})

    assert app is not None
    assert (db_base / "mor_workbench.db").exists()
