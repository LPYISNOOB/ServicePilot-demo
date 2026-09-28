param([string]$EnvironmentName = "langchain")

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $env:USERPROFILE "miniconda3\envs\$EnvironmentName\python.exe"
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python not found: $PythonPath" }

Push-Location $ProjectRoot
try {
    Write-Host "[1/3] pytest"
    & $PythonPath -m pytest
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

    Write-Host "[2/3] Running 50-case offline evaluation"
    $env:SERVICEPILOT_MODEL_MODE = "mock"
    $env:SERVICEPILOT_DB_PATH = Join-Path $ProjectRoot "data\evaluation.db"
    $env:SERVICEPILOT_CHECKPOINT_PATH = Join-Path $ProjectRoot "data\evaluation-checkpoints.db"
    & $PythonPath -m servicepilot.evaluation
    if ($LASTEXITCODE -ne 0) { throw "offline evaluation failed" }

    Write-Host "[3/3] React production build"
    Push-Location (Join-Path $ProjectRoot "frontend")
    try { npm run build } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
}
finally {
    Pop-Location
}
