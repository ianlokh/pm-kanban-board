# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-user (MVP) project management app: sign in, get a Kanban board of cards
grouped into renameable columns, and chat with an AI assistant in a sidebar that
can create, edit, move, and delete cards on your behalf. Runs as one Docker
container: FastAPI serves the statically-exported Next.js frontend at `/` and
JSON API routes under `/api`.

- Frontend: Next.js (App Router) + TypeScript + React 19 + Tailwind CSS 4, exported statically.
- Backend: Python FastAPI, `uv` for dependency management, SQLite for storage.
- AI: OpenRouter (`openai/gpt-oss-120b`), called only from the backend — the key never reaches the browser.

## Commands

### Run the whole app (Docker — the primary way to run this project)

```sh
./scripts/start.sh     # build and start; app at http://127.0.0.1:8000
./scripts/stop.sh       # stop
```

On Windows PowerShell, use `scripts/start.ps1` / `scripts/stop.ps1`. An `OPENROUTER_API_KEY`
must be present in a root `.env` file for the AI chat to work (not required for basic board
usage/health checks). Demo login is `user` / `password`.

Docker smoke test after `start.sh`:
```sh
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/health
```

### Backend (from `backend/`)

```sh
uv sync            # install deps into backend/.venv
uv run pytest      # run all backend tests
uv run pytest tests/test_board.py                # single file
uv run pytest tests/test_board.py::test_name -v  # single test
```

Backend tests do not require `OPENROUTER_API_KEY`. Database path defaults to
`backend/data/app.db`; override with `DATABASE_PATH` (useful for pointing tests
at a scratch file).

### Frontend (from `frontend/`)

```sh
npm run dev            # Next dev server; proxies /api/* to http://127.0.0.1:8000 (see next.config.ts)
npm run build           # production build (static export outside dev)
npm run lint             # ESLint
npm run test:unit        # Vitest once
npm run test:unit:watch  # Vitest watch mode
npm run test:e2e         # Playwright (tests/kanban.spec.ts)
npm run test:all         # unit tests then Playwright
```

For local frontend-only iteration, run `npm run dev` in `frontend/` alongside a
separately running backend (`uv run uvicorn app.main:app --reload` from `backend/`,
or the Dockerized backend) so the `/api/*` rewrite has something to hit.

## Architecture

### Request flow

The Next.js app is built with `output: "export"` (static HTML/JS) and copied into
`backend/static` at Docker build time (see `Dockerfile`). FastAPI (`backend/app/main.py`)
serves that static bundle at `/` and owns everything under `/api`. In development,
`next.config.ts` rewrites `/api/:path*` to `http://127.0.0.1:8000`, so the frontend
always calls relative `/api/...` paths — never hardcode a backend origin.

### Backend module layout (`backend/app/`)

- `auth.py` — SQLite connection helper (`connect_database`), schema creation
  (`initialize_database`, idempotent, called lazily by `current_user`/`authenticate`),
  password hashing (PBKDF2), and session management. Sessions are opaque tokens in
  an `HttpOnly`, `SameSite=Lax` cookie (`pm_session`), validated per-request via the
  `current_user` FastAPI dependency. The MVP seeds exactly one user (`user`/`password`).
- `board.py` — Pydantic models for the board (`BoardData`/`Column`/`Card`, all
  `extra="forbid"`) plus every board mutation (`add_card`, `edit_card`, `delete_card`,
  `move_card`, `rename_column`). **The whole board is one JSON blob per user** in the
  `boards` table (not normalized tables) — mutations read the JSON, transform it in
  Python, and write it back via `update_board(username, updater)`, which loads,
  applies a pure function, and persists atomically. `BoardData.validate_references`
  enforces the cross-reference invariants (every card in exactly one column's
  `cardIds`, card map keys match card IDs, no duplicate column/card IDs) — any new
  board mutation must preserve these on every return path.
- `assistant.py` — OpenRouter integration. `assistant_messages` builds the prompt
  (system instructions + current board JSON + bounded chat history + user message);
  the model is instructed to reply with JSON only (`{"reply": ..., "board": ...|null}`).
  `parse_assistant_result` validates that JSON against `AssistantResult`, so a full
  replacement `BoardData` (re-validated against the same invariants as above) comes
  back from the model rather than incremental edits. `save_chat_turn` persists the
  user message, the assistant reply, and (if present) the new board in one connection.
  There is exactly one conversation per user (see `conversation_messages`/`save_chat_turn`
  querying `ORDER BY id LIMIT 1`).
- `main.py` — wires the FastAPI routes to the above; also serves the SPA fallback and
  mounts `StaticFiles` for everything else under `/`.

Chat history sent to the model is bounded by `HISTORY_LIMIT` (20 messages) in
`assistant.py`; full history is still returned to the UI via `GET /api/chat`.

### Frontend layout (`frontend/src/`)

- `app/page.tsx` — top-level auth/board state machine (loading → signed-out →
  signed-in, with separate board loading/error states) and session-expiry handling
  (a 401 from any board/chat call bounces back to the login screen).
- `lib/api.ts` — the only place that calls `fetch`; every board/chat endpoint has a
  typed wrapper here that throws `ApiError` on non-2xx. New backend endpoints should
  get a corresponding wrapper here rather than inline `fetch` calls in components.
- `lib/kanban.ts` — `BoardData`/`Column`/`Card` types (must stay structurally
  compatible with the backend Pydantic models in `board.py`) and the pure
  `moveCard` reordering logic used for optimistic drag-and-drop updates before the
  server confirms.
- `components/` — `KanbanBoard` (drag-and-drop via `@dnd-kit`, owns optimistic
  updates), `KanbanColumn`, `KanbanCard`/`KanbanCardPreview`, `NewCardForm`,
  `AssistantSidebar` (chat UI, applies `board` from `ChatResponse` when present),
  `LoginForm`.
- `src/**/*.test.{ts,tsx}` — Vitest + Testing Library unit/component tests
  (config: `vitest.config.ts`, setup: `src/test/setup.ts`). `tests/kanban.spec.ts`
  at the frontend root is the Playwright end-to-end suite (`playwright.config.ts`).

### Data model

One board per user, stored as validated JSON (see `docs/DATABASE.md` and
`docs/database-schema.json` for the authoritative shape/versioning notes). Chat
messages are normalized (`conversations`, `messages` tables) so history can be
queried and bounded independently of the board blob. Board writes and their
triggering assistant message are committed together. SQLite tables are created
on demand (`initialize_database`) — there is no separate migration step for the
MVP; schema changes should keep `initialize_database` idempotent.

## Conventions

- Keep provider secrets (`OPENROUTER_API_KEY`) server-side only; the frontend must
  never receive it directly.
- Prefer editing `lib/api.ts` over scattering `fetch` calls through components.
- Board mutations (frontend `lib/kanban.ts` and backend `board.py`) must preserve
  the reference invariants described above — every card in exactly one column,
  card map keys equal card IDs, no duplicate IDs.
- No unnecessary defensive programming or speculative abstraction — this is an
  intentionally small MVP (single hardcoded user, one board per user, no migration
  framework yet). Match that scope rather than generalizing ahead of it.
- No emojis.
