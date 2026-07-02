#!/usr/bin/env bash
set -euo pipefail

output_root="${1:-dist}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"

if [[ "$output_root" != /* ]]; then
  output_root="$repo_root/$output_root"
fi

release_dir="$output_root/release"
bundle_name="MOR"
bundle_dir="$release_dir/$bundle_name"
zip_path="$output_root/MOR-macos.zip"
templates_path="$repo_root/templates"
static_path="$repo_root/static"
venv_dir="$repo_root/build/release-venv"
venv_python="$venv_dir/bin/python"
pyinstaller_root="$(mktemp -d "${TMPDIR:-/tmp}/MOR-pyinstaller.XXXXXX")"
pyinstaller_build_dir="$pyinstaller_root/work"
pyinstaller_spec_dir="$pyinstaller_root/spec"

trap 'rm -rf "$pyinstaller_root"' EXIT

rm -rf "$release_dir" "$zip_path"
mkdir -p "$release_dir" "$pyinstaller_build_dir" "$pyinstaller_spec_dir"

if [[ ! -x "$venv_python" ]]; then
  python -m venv "$venv_dir"
fi

"$venv_python" -m pip install --upgrade pip
"$venv_python" -m pip install -r requirements.txt pyinstaller

"$venv_python" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name "$bundle_name" \
  --distpath "$release_dir" \
  --workpath "$pyinstaller_build_dir" \
  --specpath "$pyinstaller_spec_dir" \
  --add-data "$templates_path:templates" \
  --add-data "$static_path:static" \
  app.py

(
  cd "$release_dir"
  zip -qr "$zip_path" "$bundle_name"
)
