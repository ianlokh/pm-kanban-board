# Code Review

Date: 2026-08-30
Scope: full repository at commit `39107b3` (backend, frontend, Docker/scripts, docs, tests). ~3,500 lines of source excluding lockfiles and build output.

**Update (2026-08-30):** All High and Medium findings (#1-#4) have been remediated — see "Remediation status" below. Low-priority and docs items (#5-#11) are still open.

## Summary

The codebase is small, consistent with its documented MVP scope, and largely matches what `CLAUDE.md` describes. Board mutations are protected by a single Pydantic validator that every write path (including the AI's own output) is re-checked against, SQL is fully parameterized, and React never bypasses its default escaping, so no injection or XSS issues were found. The test suite (pytest + Vitest + Playwright) covers the golden paths well.

The issues below are mostly about two things: a network-exposure gap between the stated "runs locally on your own machine" intent and the actual Docker port binding, and a couple of read-modify-write races that can silently drop a change when the AI assistant and manual board edits overlap. Nothing here requires a redesign; each fix is small and localized.

| # | Severity | Area | Finding |
|---|----------|------|---------|
| 1 | High | Docker/security | `docker-compose.yml` binds port 8000 on all interfaces, not just loopback |
| 2 | High | Backend correctness | Assistant reply and concurrent board edits can silently overwrite each other (lost update) |
| 3 | Medium | Frontend correctness | `AssistantSidebar` refetches chat history on every board change due to an unstable callback dependency |
| 4 | Medium | Frontend convention | `LoginForm` and session check/logout call `fetch` directly instead of going through `lib/api.ts` |
| 5 | Low | Backend security | Session cookie has no `secure` flag |
| 6 | Low | Backend robustness | Card/column text fields have no `max_length` |
| 7 | Low | Backend hygiene | Expired sessions are never proactively cleaned up |
| 8 | Low | Frontend correctness | Optimistic-update revert can briefly flash stale state when mutations are queued |
| 9 | Low | Backend security | No rate limiting on `/api/auth/login` |
| 10 | Docs | Accuracy | `frontend/AGENTS.md` describes a pre-backend, demo-only frontend that no longer exists |
| 11 | Docs | Hygiene | `backend/AGENTS.md` and `scripts/AGENTS.md` are empty placeholders |

## Findings

### 1. Docker Compose exposes the app beyond localhost (High)

`docker-compose.yml:11-12`:

```yaml
    ports:
      - "8000:8000"
```

Docker's `"8000:8000"` shorthand binds the container port to `0.0.0.0:8000` on the host — every interface, not just loopback. Combined with the app's single hardcoded login (`user` / `password`, documented in `README.md`) and no rate limiting (see #9), anyone on the same network (Wi-Fi, office LAN, cloud VM with an open security group) can reach the board and, if `OPENROUTER_API_KEY` is set, spend the owner's OpenRouter credits. This contradicts the stated design ("This app is intended to run locally on your own machine," `README.md:81`) and `start.sh`'s own printed URL (`http://127.0.0.1:8000`).

**Fix:** bind explicitly to loopback:

```yaml
    ports:
      - "127.0.0.1:8000:8000"
```

### 2. Lost-update races between the AI assistant and concurrent board edits (High)

Two related gaps in `backend/app/board.py` and `backend/app/assistant.py`:

- `update_board` (`board.py:140-162`) reads the board row, runs the pure updater in Python, then writes it back. The `SELECT` and the following `INSERT ... ON CONFLICT DO UPDATE` are not wrapped in an explicit transaction that locks across the read, so two concurrent mutations (e.g., two browser tabs, or a drag firing while another request is still in flight) can both read the same stale row; the second write silently discards the first's change.
- `chat()` (`main.py:143-156`) reads the board once at the start of the request, then calls OpenRouter with a timeout of up to 30 seconds (`assistant.py:46`). When the model replies, `save_chat_turn` (`assistant.py:118-156`) unconditionally writes `result.board` — a full snapshot built from that stale pre-call board — back to the `boards` row. Anything the user did via `/api/board/*` in the seconds while the assistant was "thinking" is overwritten without warning.

Given this is presented as an interactive assistant that edits the board while the user can keep working, the second case is the more likely to actually bite a real user.

**Fix options, from smallest to most complete:**
- Wrap the read + write of `update_board` in a single `BEGIN IMMEDIATE` transaction on one connection so concurrent writers serialize instead of racing.
- For the assistant path, either re-read the board immediately before applying `result.board` and merge/reject on conflict, or store a version/`updated_at` alongside the board and have `save_chat_turn` refuse to apply a stale result (surfacing a "board changed, please retry" error instead of clobbering).

### 3. `AssistantSidebar` refetches chat history on every board change (Medium)

`frontend/src/app/page.tsx:100`:

```tsx
<AssistantSidebar onBoardUpdate={setBoard} onSessionExpired={() => { setBoard(null); setAuthState("signed-out"); }} />
```

`onSessionExpired` is a new arrow function on every render of `Home`. `AssistantSidebar`'s effect depends on it:

`frontend/src/components/AssistantSidebar.tsx:27-38`:

```tsx
useEffect(() => {
  getChatHistory()
    .then(setMessages)
    .catch(...)
    .finally(() => setIsLoading(false));
}, [onSessionExpired]);
```

`Home` re-renders on every `setBoard` call — which happens after *every* card drag, edit, add, delete, rename, and assistant reply. Each of those re-renders creates a new `onSessionExpired` reference, re-running the effect and firing an extra `GET /api/chat`, toggling `isLoading` and briefly re-rendering the message list even though nothing about the chat actually changed. It's wasted network traffic today and a visible flicker risk as history grows.

**Fix:** wrap the callback with `useCallback` in `page.tsx` (it only needs `[]` — it doesn't close over anything that changes), or have the effect not depend on a value it only needs inside its own error branch.

### 4. `LoginForm` and page-level auth calls bypass `lib/api.ts` (Medium)

`CLAUDE.md` documents `lib/api.ts` as "the only place that calls `fetch`... New backend endpoints should get a corresponding wrapper here rather than inline `fetch` calls in components." Three call sites don't follow this:

- `frontend/src/components/LoginForm.tsx:25` — `fetch("/api/auth/login", ...)`
- `frontend/src/app/page.tsx:38` — `fetch("/api/auth/me", { credentials: "include" })`
- `frontend/src/app/page.tsx:60` — `fetch("/api/auth/logout", { method: "POST", credentials: "include" })`

Beyond the convention drift, this means the login flow's error handling diverges from the rest of the app: it doesn't throw `ApiError`, so a 401 here can't be told apart from other failures the way `KanbanBoard`/`AssistantSidebar` already do for board/chat calls.

**Fix:** add `login`, `logout`, and `me` wrappers to `api.ts` (mirroring the existing `request<T>` helper) and use them from `LoginForm` and `page.tsx`.

### 5. Session cookie has no `secure` flag (Low)

`backend/app/main.py:67-73`:

```python
response.set_cookie(
    SESSION_COOKIE,
    token,
    expires=expires_at,
    httponly=True,
    samesite="lax",
)
```

Fine for the current plain-HTTP, loopback-only story. If this is ever put behind HTTPS or served on a non-loopback address, the session token would still be sendable over an unencrypted connection. Consider gating `secure=True` behind an env var (e.g., `SECURE_COOKIES`) so it's a one-line change when the deployment story changes, rather than a thing to remember.

### 6. No `max_length` on card/column text fields (Low)

`backend/app/board.py`: `Card.title`/`details`, `Column.title`, `CardCreateRequest`, `CardUpdateRequest`, `ColumnRenameRequest` all use `min_length=1` but no upper bound. `AssistantRequest.message` already sets a precedent (`max_length=4000`, `assistant.py:18`). Because the whole board is one JSON blob read/written on every request (`board.py:110-162`), an unbounded title/details value bloats that blob for every subsequent read. Low risk given the single-user scope, but a quick, consistent fix.

### 7. Expired sessions are never proactively cleaned up (Low)

`backend/app/auth.py:119-122` only deletes a session row when that exact expired token is presented again:

```python
expires_at = datetime.fromisoformat(row["expires_at"])
if expires_at <= now:
    connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
    raise HTTPException(status_code=401, detail="Authentication required")
```

Tokens that are simply abandoned (browser closed, cookie cleared) stay in `sessions` forever. Harmless at MVP scale; worth a periodic `DELETE FROM sessions WHERE expires_at < ?` (e.g., opportunistically inside `create_session`) if this runs long-lived.

### 8. Optimistic-update revert can flash stale state (Low)

`frontend/src/components/KanbanBoard.tsx:53-79`. Mutations are correctly serialized through `mutationQueue`, but each queued `persist(previous, request)` call captures `previous` as the board state *at the moment the action was initiated*. If an earlier queued mutation fails while a later one is already in flight or has succeeded, the failure handler calls `setBoard(previous)`, which can briefly discard the later mutation's optimistic UI before the next queued response resets state from the server. This is self-healing (the next successful response overwrites it with server truth) and not a data-loss bug, but it's a visible flicker under fast, back-to-back edits combined with a network error. Consider reverting only the failed mutation's own delta, or refetching from the server on failure instead of reverting to a captured snapshot.

### 9. No rate limiting on login (Low)

`backend/app/main.py:59-74`. Combined with #1 (LAN-reachable by default) and a fixed, publicly documented password, online guessing is trivial today. The credentials are intentionally public knowledge for this MVP (`README.md:65-68`), so this is low priority as long as #1 is fixed and the app stays on a trusted network — but worth a note if this is ever exposed more broadly.

## Documentation

### 10. `frontend/AGENTS.md` is stale

`frontend/AGENTS.md:5` and `:20` describe the frontend as it was *before* the backend existed:

> "authentication and backend persistence are not implemented yet"
> "the current state is lost on refresh because there is no API or database integration"

Neither is true anymore — `page.tsx` implements the full auth/session state machine, and every `KanbanBoard` mutation persists through `lib/api.ts`. Anyone (human or agent) reading this file for orientation will be misled about the current architecture. Update it to match `CLAUDE.md`'s frontend section, or remove it in favor of the root `CLAUDE.md`.

### 11. `backend/AGENTS.md` and `scripts/AGENTS.md` are empty

Both are 0-byte placeholder files. Either fill them in with directory-specific guidance (the way `frontend/AGENTS.md` was intended to, before it went stale) or remove them — an empty file with no signal is more confusing than no file.

## Test coverage gaps

- No backend test for the 404 paths of `rename_column`, `add_card`, `edit_card`, `delete_card`, or `move_card` when the target column/card doesn't exist.
- No API-level test for reordering cards *within* a column via `/api/board/move` (only covered indirectly by the pure-function test in `kanban.test.ts` and one cross-column API test in `test_board.py`).
- No frontend unit test for the 401/`onSessionExpired` branch in `KanbanBoard` or `AssistantSidebar` (only exercised end-to-end via Playwright's logout test, which doesn't specifically trigger a mid-session 401).
- No regression test for the lost-update race in finding #2 — understandably hard to assert deterministically against SQLite in a unit test, but worth a comment noting the gap once a fix lands, so a future refactor doesn't reintroduce it.

## What's solid (worth preserving)

- `BoardData.validate_references` (`board.py:32-45`) is enforced on every mutation path *and* re-applied to whatever the AI returns (`assistant.py` reuses the same `BoardData` model) — a simple, effective guardrail against both hand-written bugs and prompt-injection-driven invalid state.
- Every SQL statement across `auth.py`, `board.py`, and `assistant.py` is parameterized; no injection surface found.
- No `dangerouslySetInnerHTML` or equivalent anywhere in the frontend; card/message content is always rendered as text, so no XSS surface found.
- `.env` is correctly gitignored and was never committed (verified via `git log --all -- .env`).
- Module boundaries match `CLAUDE.md`'s description closely, and the `lib/api.ts` single-fetch-point pattern is followed everywhere except the three call sites in finding #4.
- Good layered test coverage of the golden paths: pytest + `TestClient` for the API, Vitest + Testing Library for components and pure logic, Playwright for real drag-and-drop and auth flows.

## Remediation status

| # | Severity | Finding | Status | Fix |
|---|----------|---------|--------|-----|
| 1 | High | Docker Compose exposes the app beyond localhost | Fixed | `docker-compose.yml` now binds `127.0.0.1:8000:8000` instead of `8000:8000`. |
| 2 | High | Lost-update races between the AI assistant and concurrent board edits | Fixed | `update_board` (`board.py`) now wraps its read + write in a `BEGIN IMMEDIATE` transaction, serializing concurrent mutations; `connect_database()` (`auth.py`) sets `PRAGMA busy_timeout = 5000` so a second writer waits instead of erroring. The assistant path (`save_chat_turn` in `assistant.py`) now does a compare-and-swap `UPDATE ... WHERE board_json = <board it originally read>`; if the board changed while the model was replying, the whole turn rolls back and `/api/chat` returns `409` instead of silently overwriting the concurrent edit. Covered by a new regression test, `test_chat_rejects_stale_board_instead_of_clobbering_concurrent_edit` in `backend/tests/test_assistant.py`. |
| 3 | Medium | `AssistantSidebar` refetches chat history on every board change | Fixed | `page.tsx` now defines `handleSessionExpired` once via `useCallback(..., [])` and passes that stable reference to both `KanbanBoard` and `AssistantSidebar`, instead of a fresh arrow function per render. |
| 4 | Medium | `LoginForm` and page-level auth calls bypass `lib/api.ts` | Fixed | Added `login`, `logout`, and `me` wrappers (plus an exported `User` type) to `lib/api.ts`. `LoginForm.tsx` and `page.tsx` now call these instead of `fetch` directly, so auth errors surface as `ApiError` like every other call site. |

Verified after the fixes: `uv run pytest` (15 passed, including the new regression test), `npm run lint` (clean), `npm run test:unit` (8 passed), `npm run build` (succeeds), `npm run test:e2e` (6 passed), and `docker compose config` (confirms the port now binds to `host_ip: 127.0.0.1`).

## Suggested priority order

1. Fix the Docker port binding (#1) — one line, closes a real exposure gap.
2. Decide on a fix for the assistant/board race (#2) — the most likely to cause a user-visible "my change disappeared" report.
3. Fix the `AssistantSidebar` dependency bug (#3) — small, removes redundant traffic and flicker.
4. Route `LoginForm`/`page.tsx` auth calls through `lib/api.ts` (#4) — brings the codebase back in line with its own documented convention.
5. Refresh or remove `frontend/AGENTS.md` (#10) — cheap, prevents future confusion.
6. Everything else (#5-9, #11) is low-priority hardening; batch it whenever convenient.
