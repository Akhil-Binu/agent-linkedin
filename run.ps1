# LinkedBot PowerShell Launcher
$ErrorActionPreference = "Stop"
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    & $venvPython (Join-Path $PSScriptRoot "menu.py")
} else {
    python (Join-Path $PSScriptRoot "menu.py")
}
