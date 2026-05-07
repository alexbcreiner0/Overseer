param(
    [string]$AppName
)

if (-not $AppName) {
    Write-Host "Usage: .\build_exe.ps1 APP_NAME"
    exit 1
}

Set-Location $PSScriptRoot

pyinstaller `
  -n $AppName `
  --clean `
  --noconfirm `
  --additional-hooks-dir=. `
  --collect-data overseer `
  --icon ../../../src/overseer/assets/icon.ico `
  --collect-data scienceplots `
  --hidden-import overseer.tools.log_formatter `
  --paths ..\..\..\src `
  --windowed `
  .\main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller build failed."
    exit 1
}
