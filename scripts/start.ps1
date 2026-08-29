$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)
docker compose up --build -d
Write-Output "Project Management MVP is running at http://127.0.0.1:8000"
