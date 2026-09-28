param(
    [string]$EnvironmentName = "langchain",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $env:USERPROFILE "miniconda3\envs\$EnvironmentName\python.exe"
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python not found: $PythonPath" }

$Arguments = @("-m", "uvicorn", "servicepilot.api:app", "--host", "127.0.0.1", "--port", "8000")
if ($Reload) { $Arguments += "--reload" }
Push-Location $ProjectRoot
try { & $PythonPath @Arguments } finally { Pop-Location }
