# Start the application using the project virtual environment.
# Usage: .\run.ps1 [-AllowNonCommercial] [extra uvicorn arguments]
#   -AllowNonCommercial  Make non-commercial (CC BY-NC, e.g. GNoME) data available
#                        as an opt-in option in the UI. Disabled by default.
param(
    [switch]$AllowNonCommercial,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$UvicornArgs
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if ($AllowNonCommercial) {
    $env:ALLOW_NON_COMMERCIAL = "1"
}

$VenvPython = "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found. Run .\setup.ps1 first."
}

$AppHost = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
$Port = if ($env:PORT) { $env:PORT } else { "8000" }

& $VenvPython -m uvicorn app.main:app --host $AppHost --port $Port @UvicornArgs
