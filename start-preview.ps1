$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$previewPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $previewPython)) {
    throw 'Create .venv and install requirements.txt first; see README.md.'
}
& $previewPython run_preview.py
