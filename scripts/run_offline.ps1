# scripts/run_offline.ps1
#
# Starts the backend in offline mode for this PowerShell session only.
# OFFLINE_MODE is set on the process environment, not written to .env,
# so it does not persist after this session closes.
#
# Run from anywhere:  .\scripts\run_offline.ps1
# If PowerShell blocks the script, allow local scripts for this session:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Stop on the first error.
$ErrorActionPreference = "Stop"

# Move to the backend root (the parent of the scripts folder), so the
# venv and "app.main" resolve correctly regardless of where this was called.
$BackendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $BackendRoot

# 1. Activate the virtual environment. Adjust the path if your venv
#    lives somewhere else (for example, "venv" instead of ".venv").
$VenvActivate = Join-Path $BackendRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $VenvActivate)) {
    throw "Virtual environment not found at $VenvActivate. Create it first."
}
& $VenvActivate

# 2. Enable offline mode for this process only. Settings reads this
#    environment variable, which takes precedence over .env.
$env:OFFLINE_MODE = "true"

# 3. Start the API server with auto-reload on port 8000.
uvicorn app.main:app --reload --port 8000