from __future__ import annotations

import base64
import hashlib
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VENDORED_HTMX = ROOT / "static" / "js" / "vendor" / "htmx.min.js"

# Subresource-integrity hash previously pinned in templates/_head_assets.html
# for https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js. Kept here so the
# vendored copy stays provably identical to the published release.
HTMX_SHA384 = "D1Kt99CQMDuVetoL1lrYwg5t+9QdHe7NLX/SoJYkXDFfX37iInKRy5xLSi8nO7UC"

# src="http://..." / href='https://...' inside a <script>/<link> tag.
EXTERNAL_ASSET_RE = re.compile(
    r"""<(?:script|link)\b[^>]*?\b(?:src|href)\s*=\s*["']\s*(https?:)?//""",
    re.IGNORECASE | re.DOTALL,
)


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


def test_htmx_is_vendored_locally():
    assert VENDORED_HTMX.is_file(), f"missing vendored htmx at {VENDORED_HTMX}"

    digest = base64.b64encode(hashlib.sha384(VENDORED_HTMX.read_bytes()).digest()).decode()
    assert digest == HTMX_SHA384, (
        "vendored htmx.min.js does not match the pinned htmx 1.9.10 release hash"
    )


def test_vendored_assets_are_not_git_ignored():
    result = subprocess.run(
        ["git", "check-ignore", "static/js/vendor/htmx.min.js"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, (
        "static/js/vendor/htmx.min.js is excluded by .gitignore, so it would be "
        "missing from clean checkouts and release builds"
    )


def test_release_scripts_bundle_the_whole_static_tree():
    """Both build scripts --add-data the static/ dir, so vendor/ ships for free."""
    ps1 = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8")
    sh = (ROOT / "scripts" / "build_release.sh").read_text(encoding="utf-8")

    assert '$staticPath = Join-Path $repoRoot "static"' in ps1
    assert '--add-data "$staticPath;static"' in ps1
    assert 'static_path="$repo_root/static"' in sh
    assert '--add-data "$static_path:static"' in sh


def test_templates_reference_no_external_assets():
    offenders = []
    for template in sorted((ROOT / "templates").rglob("*.html")):
        text = template.read_text(encoding="utf-8")
        for match in EXTERNAL_ASSET_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{template.relative_to(ROOT).as_posix()}:{line}")

    assert not offenders, (
        "templates must load assets from static/ only (MOR runs offline); "
        f"external references found at: {offenders}"
    )
