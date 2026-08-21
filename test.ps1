# Run the test suite using the project virtual environment.
# Usage: .\test.ps1 [extra pytest arguments]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PytestArgs)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$VenvPython = "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found. Run .\setup.ps1 first."
}

& $VenvPython -m pytest @PytestArgs
