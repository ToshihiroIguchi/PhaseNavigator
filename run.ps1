# Start the application using the project virtual environment.
# Usage: .\run.ps1 [extra uvicorn arguments]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$UvicornArgs)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$VenvPython = "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found. Run .\setup.ps1 first."
}

$AppHost = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
$Port = if ($env:PORT) { $env:PORT } else { "8000" }

& $VenvPython -m uvicorn app.main:app --host $AppHost --port $Port @UvicornArgs
