param(
    [string]$EnvironmentName = "langchain",
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $env:USERPROFILE "miniconda3\envs\$EnvironmentName\python.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Conda environment Python not found: $PythonPath"
}

Write-Host "[1/3] Installing ServicePilot Python dependencies"
& $PythonPath -m pip install -e "$ProjectRoot[dev]"

Write-Host "[2/3] Initializing synthetic database"
& $PythonPath -m servicepilot.seed

if (-not $SkipFrontend) {
    Write-Host "[3/3] Installing and building React frontend"
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        npm install
        npm run build
    }
    finally {
        Pop-Location
    }
}

Write-Host "Setup complete. Backend: .\scripts\start-backend.ps1; frontend: .\scripts\start-frontend.ps1"
