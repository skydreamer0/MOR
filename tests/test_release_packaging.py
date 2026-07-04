from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_pyinstaller_temp_paths_stay_on_repo_drive():
    script = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8")

    assert "$pyinstallerRoot = Join-Path $repoRoot" in script
    assert "Join-Path $env:TEMP" not in script


def test_macos_release_script_is_tracked_executable():
    result = subprocess.run(
        ["git", "ls-files", "--stage", "scripts/build_release.sh"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    mode = result.stdout.split()[0]
    assert mode == "100755"
