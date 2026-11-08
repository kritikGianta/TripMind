# Runs the API without Docker, for frontend work: same code and .env, but a local SQLite demo
# database and no worker, Redis or monitoring. `npm run dev` reaches it on port 8000 by default.
# Docker Desktop must be fully quit first, because it holds port 8000 even when idle.
#
#   powershell -ExecutionPolicy Bypass -File scripts\local-api.ps1
param([int]$Port = 8000)

$backend = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"
$database = Join-Path $backend "local-dev.db"
if (-not (Test-Path $database)) {
    Write-Error "$database not found. It is a git-ignored copy of a loaded demo database; see docs/operations.md."
    exit 1
}

Set-Location $backend
$env:DATABASE_URL = "sqlite:///" + ($database -replace "\\", "/")
& ".venv\Scripts\python.exe" -m uvicorn app.main:create_app --factory --port $Port --log-level warning
