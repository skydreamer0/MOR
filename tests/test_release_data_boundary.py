from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _tracked_files(*patterns: str) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={PROJECT_ROOT}",
            "ls-files",
            *patterns,
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_release_does_not_track_local_excel_or_database_files():
    tracked = _tracked_files("*.xlsx", "*.db", "*.sqlite", "*.sqlite3")

    assert tracked == []
