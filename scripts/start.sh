#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

docker compose up --build -d
printf '%s\n' "Project Management MVP is running at http://127.0.0.1:8000"
