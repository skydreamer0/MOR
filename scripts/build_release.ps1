param(
    [string]$OutputRoot = "dist"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot $OutputRoot
}

$releaseDir = Join-Path $OutputRoot "release"
$bundleName = "MOR"
$bundleDir = Join-Path $releaseDir $bundleName
$zipPath = Join-Path $OutputRoot "MOR-windows.zip"
$templatesPath = Join-Path $repoRoot "templates"
$staticPath = Join-Path $repoRoot "static"
$venvDir = Join-Path $repoRoot "build\\release-venv"
$venvPython = Join-Path $venvDir "Scripts\\python.exe"
$pyinstallerRoot = Join-Path $repoRoot ("build\\pyinstaller-" + [guid]::NewGuid().ToString("N"))
$pyinstallerBuildDir = Join-Path $pyinstallerRoot "work"
$pyinstallerSpecDir = Join-Path $pyinstallerRoot "spec"

if (Test-Path $releaseDir) {
    Remove-Item $releaseDir -Recurse -Force
}
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

New-Item -ItemType Directory -Path $pyinstallerBuildDir -Force | Out-Null
New-Item -ItemType Directory -Path $pyinstallerSpecDir -Force | Out-Null

New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

if (-not (Test-Path $venvPython)) {
    python -m venv $venvDir
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt pyinstaller

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name $bundleName `
    --distpath $releaseDir `
    --workpath $pyinstallerBuildDir `
    --specpath $pyinstallerSpecDir `
    --add-data "$templatesPath;templates" `
    --add-data "$staticPath;static" `
    app.py

Compress-Archive -Path $bundleDir -DestinationPath $zipPath -Force
