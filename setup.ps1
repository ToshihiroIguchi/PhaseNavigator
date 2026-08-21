# Create (or refresh) the project virtual environment and install dependencies.
#
# Usage:
#   .\setup.ps1                    # create venv and install requirements
#   .\setup.ps1 -WithPmgAddons     # also build the optional pymatgen add-ons
#   .\setup.ps1 -PythonBin python3.13
param(
    [string]$PythonBin = "python",
    [switch]$WithPmgAddons
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$VenvDir = "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Get-Command $PythonBin -ErrorAction SilentlyContinue)) {
    Write-Error "'$PythonBin' not found. Install Python 3.11 or newer."
}

# pymatgen, mp-api and emmet-core require Python 3.11 or newer.
$pyVersion = & $PythonBin -c "import sys; print('{}.{}'.format(sys.version_info[0], sys.version_info[1]))"
$parts = $pyVersion.Split('.')
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 11)) {
    Write-Error "Python 3.11+ is required, found $pyVersion."
}

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment in .\$VenvDir ..."
    & $PythonBin -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create the virtual environment." }
}

Write-Host "Installing dependencies with $VenvPython ..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to upgrade pip." }
& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install requirements." }

# The optional pymatgen add-ons (enumlib, bader) are not used by the phase diagram
# pipeline. They need a Fortran toolchain and often fail on Windows, so they are opt-in.
if ($WithPmgAddons) {
    $pmg = Join-Path $VenvDir "Scripts\pmg.exe"
    foreach ($addon in @("enumlib", "bader")) {
        Write-Host "Installing optional pymatgen add-on: $addon ..."
        & $pmg config --install $addon
        if ($LASTEXITCODE -ne 0) { Write-Warning "'pmg config --install $addon' failed; continuing." }
    }
}

Write-Host ""
Write-Host "Done. Use the wrapper scripts, or activate the environment with:"
Write-Host "  .\venv\Scripts\Activate.ps1"
