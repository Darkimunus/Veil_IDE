$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Icon = Join-Path $Root "favicon.ico"
$Py = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
  Write-Host "No .venv - running uv sync --group dev ..."
  uv sync --group dev
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $Py -m PyInstaller `
  --noconfirm `
  --windowed `
  --name Veil_IDE `
  --icon $Icon `
  --paths $Root `
  --add-data "config\default.toml;config" `
  --add-data "favicon.ico;." `
  --collect-all PySide6 `
  --collect-all shiboken6 `
  main.py

if ($LASTEXITCODE -ne 0) {
  Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
  exit $LASTEXITCODE
}

Write-Host "Built: $Root\dist\Veil_IDE\Veil_IDE.exe"
