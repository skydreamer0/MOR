"""Run the node:test suites covering static/js modules.

The frontend stays build-step-free (ADR-0001); node is only needed to run
tests, so this wrapper skips cleanly when node is not installed.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_frontend_js_unit_tests() -> None:
    test_files = sorted(str(p) for p in (ROOT / "tests" / "js").glob("*.test.js"))
    assert test_files, "no JS test files found under tests/js/"
    result = subprocess.run(
        ["node", "--test", *test_files],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, f"node --test failed:\n{result.stdout}\n{result.stderr}"
