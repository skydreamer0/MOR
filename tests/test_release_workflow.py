from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_workflow_targets_windows_and_macos_and_packages_artifacts():
    workflow = PROJECT_ROOT / ".github/workflows/release.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "windows-latest" in text
    assert "macos-latest" in text
    assert "upload-artifact" in text


def test_release_build_scripts_exist_and_call_pyinstaller():
    windows_script = PROJECT_ROOT / "scripts/build_release.ps1"
    mac_script = PROJECT_ROOT / "scripts/build_release.sh"

    windows_text = windows_script.read_text(encoding="utf-8")
    mac_text = mac_script.read_text(encoding="utf-8")

    assert "PyInstaller" in windows_text
    assert "PyInstaller" in mac_text
