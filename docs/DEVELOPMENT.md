# Local Development

## Backend tests

The backend uses `uv` for dependency management and `pytest` for tests:

```bash
cd backend
uv sync
uv run pytest
```

## Docker smoke test

From the repository root:

```bash
./scripts/start.sh
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/health
./scripts/stop.sh
```

On Windows PowerShell, use `scripts/start.ps1` and `scripts/stop.ps1` instead.

The container reads `OPENROUTER_API_KEY` from the root `.env` file when it is available. The key is not required for the Part 2 health check and must not be committed.

## API surface

Authenticated users can read and mutate their board through `/api/board` and can use `/api/chat` for persisted assistant conversations. Board changes are validated and stored in SQLite; the assistant requires `OPENROUTER_API_KEY` and keeps that key server-side.
