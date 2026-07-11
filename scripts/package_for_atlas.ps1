$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $repoRoot "dist"
$outFile = Join-Path $outDir "robot-phone-control-atlas.zip"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $outFile) {
    Remove-Item $outFile
}

$include = @(
    "server",
    "tools",
    "docs",
    "scripts",
    "systemd",
    "requirements.txt",
    "requirements-rapidocr-atlas.txt",
    "README.md",
    "PROJECT_NOTES.md",
    ".gitignore"
)

$tempDir = Join-Path $outDir "atlas-package"
if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir
}
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

foreach ($item in $include) {
    $src = Join-Path $repoRoot $item
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $tempDir -Recurse -Force
    }
}

Get-ChildItem -Path $tempDir -Recurse -Directory -Force |
    Where-Object { $_.Name -in @("__pycache__", ".pytest_cache") } |
    Remove-Item -Recurse -Force

Get-ChildItem -Path $tempDir -Recurse -File -Force |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
    Remove-Item -Force

& tar.exe -a -c -f $outFile -C $tempDir .
if ($LASTEXITCODE -ne 0) {
    throw "tar.exe failed with exit code $LASTEXITCODE"
}
Remove-Item -Recurse -Force $tempDir

Write-Host "Created: $outFile"
