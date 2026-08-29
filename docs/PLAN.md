# Project Plan

## Decisions and guardrails

- The app will run in one production Docker container. FastAPI will serve the statically exported Next.js site at `/` and expose JSON API routes under `/api`; this keeps local deployment simple and avoids cross-origin configuration in the MVP.
- Development may still use the existing Next.js dev server and a local FastAPI process when that is useful for fast feedback. The start and stop scripts will primarily manage the Docker deployment and will have Mac/Linux and Windows-compatible entry points where practical.
- Authentication will use a server-side session stored in SQLite and an `HttpOnly`, `SameSite=Lax` cookie. The MVP accepts only `user` / `password`; the schema will still include a user identifier so more users can be added later.
- The Kanban board and AI conversation history will be persisted in SQLite. Board state will be stored as validated JSON matching the frontend `BoardData` shape; conversation messages will be stored as separate records so history can be queried and bounded for an AI request.
- OpenRouter calls will use `openai/gpt-oss-120b` and read `OPENROUTER_API_KEY` from the environment. Secrets must never be committed, logged, or sent to the browser.
- Every part below is an implementation gate. The agent checks off implementation items and records test results, then pauses for explicit approval where marked before proceeding to the next gated part.

## Part 1: Plan and frontend documentation

### Checklist

- [x] Expand this plan into implementation steps, tests, and success criteria.
- [x] Record the authentication, persistence, Docker, and AI decisions above.
- [x] Add `frontend/AGENTS.md` describing the existing frontend architecture and commands.
- [ ] Get user approval for this plan before changing application code.

### Tests and checks

- Confirm the documented frontend commands match `frontend/package.json`.
- Run the existing frontend unit suite after documentation work; no application behavior should change.

### Success criteria

- The plan is specific enough to implement one part at a time without re-deciding the architecture.
- The user has explicitly approved the plan.

## Part 2: Docker and FastAPI scaffolding

### Checklist

- [x] Create the FastAPI application package, dependency metadata, and development configuration using `uv`.
- [x] Add `GET /api/health` returning a small JSON health response.
- [x] Add a temporary static `index.html` served at `/` so the container can be checked before the Next.js export exists.
- [x] Add a Dockerfile with a reproducible backend runtime and `.dockerignore`.
- [x] Add Docker Compose configuration if it materially simplifies local environment variables and volume handling.
- [x] Add start and stop entry points under `scripts/` for the supported host shells; make them fail clearly when Docker is unavailable.
- [x] Document required environment variables without putting secret values in tracked files.

### Tests and checks

- [x] Use `pytest` and FastAPI's test client for the health route and static response.
- [x] Build the image and start the container using the start script.
- [x] Verify `/` returns the example HTML and `/api/health` returns JSON from the running container.
- [x] Stop the container using the stop script and verify it exits cleanly.

### Success criteria

- [x] A clean checkout can build and run the container locally with documented commands.
- [x] The root page and API health check are served by FastAPI from the container.
- [x] Backend tests run through `pytest` without requiring OpenRouter credentials.

## Part 3: Serve the existing frontend

### Checklist

- [x] Configure Next.js for a static export compatible with the FastAPI serving layout.
- [x] Preserve the current `KanbanBoard` demo and its client-side interactions at `/`.
- [x] Copy the generated static assets into the runtime image and configure static fallback behavior.
- [x] Keep API calls same-origin under `/api` so the production container needs no CORS setup.
- [x] Add a production build path that does not rely on the Next.js development server.

### Tests and checks

- [x] Run `npm run lint`, `npm run test:unit`, and `npm run build` in `frontend/`.
- [x] Run the Playwright suite, including authenticated board rendering, add, drag/drop, invalid login, refresh, and logout.
- [x] Build and run the Docker image and repeat the root-page/API smoke check.

### Success criteria

- [x] The demo board renders at `/` from the FastAPI-served static export.
- [x] Existing board behavior remains intact in both unit and browser tests.
- [x] The production container serves all required JavaScript and CSS assets without 404s.

## Part 4: MVP sign-in and sign-out

### Checklist

- [x] Add the minimal SQLite session model and a server-side session service.
- [x] Add `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/auth/logout` routes.
- [x] Accept only `user` / `password` for the MVP and return a generic authentication error for invalid credentials.
- [x] Set and clear an `HttpOnly`, `SameSite=Lax` session cookie with an appropriate local-development configuration.
- [x] Add a login screen for unauthenticated users and a logout control for authenticated users.
- [x] Protect the board UI boundary; defer board API authorization to Part 6 when those routes exist.

### Tests and checks

- [x] `pytest` tests for valid login, invalid login, session lookup, logout, and protected-route rejection.
- [x] Frontend unit tests for login and error state.
- [x] Playwright tests for first visit, failed credentials, successful login, refresh persistence, and logout.
- [x] Verify the cookie is not readable by browser JavaScript through the `HttpOnly` flag.

### Success criteria

- [x] `/` shows login before the board for a new browser session.
- [x] `user` / `password` grants access, survives refresh, and can be revoked by logout.
- [x] An unauthenticated session sees the login UI rather than the board; board API protection is deferred to Part 6.

## Part 5: Database model and approval

### Checklist

- [x] Propose and save a JSON schema document in `docs/` describing users, sessions, boards, and chat conversations/messages.
- [x] Define the board JSON contract using stable IDs, ordered column `cardIds`, and a cards map, with validation rules for references and required strings.
- [x] Define ownership and uniqueness constraints: one board per user for the MVP, with room for additional boards later.
- [x] Define session expiration, message roles, timestamps, and the maximum history sent to the model.
- [x] Document SQLite initialization, migrations/versioning, database path configuration, and backup/development behavior.
- [ ] Pause for explicit user sign-off on the schema before implementing board persistence.

### Tests and checks

- [x] Validate the schema document as JSON.
- [x] Review representative valid and invalid board payloads against the documented rules.
- [x] Confirm the model supports the one-board-per-user MVP and future multi-user ownership.

### Success criteria

- The schema is a tracked, human-readable JSON artifact with matching explanatory documentation.
- The user approves the schema before Part 6 begins.

## Part 6: Persistent board backend

### Checklist

- [ ] Initialize the SQLite database automatically when the configured file does not exist.
- [ ] Implement board read and update routes for the authenticated user, using the session identity rather than a client-supplied user ID.
- [ ] Add routes or operations for column renames, card creation/editing/deletion, and card movement while preserving board invariants.
- [ ] Validate every incoming board mutation and return clear `4xx` responses for malformed or unauthorized data.
- [ ] Use transactions for board updates so a failed write cannot leave columns and cards inconsistent.
- [ ] Seed the authenticated user's first board from the existing demo data when no board exists.

### Tests and checks

- `pytest` tests for database creation, seeding, reads, every mutation, invalid references, ownership isolation, and transaction rollback.
- Test the API with an isolated temporary SQLite database for every test session.
- Add coverage for concurrent or repeated updates where the chosen SQLite approach requires it.

### Success criteria

- A missing database is created automatically and a new user receives a valid initial board.
- Board reads and writes are authenticated, validated, durable, and isolated by user.
- Backend tests pass without network access.

## Part 7: Frontend backed by the API

### Checklist

- [ ] Replace the board's local initial state with an authenticated fetch from the board API.
- [ ] Add loading, empty, error, and retry states without changing the established board interactions.
- [ ] Persist column renames, card edits, card creation/deletion, and drag/drop through the API.
- [ ] Keep optimistic UI behavior only where rollback is defined; otherwise update from the successful server response.
- [ ] Handle session expiration by returning the user to login without losing unrelated local UI state.
- [ ] Add a small API client layer with typed request/response contracts.

### Tests and checks

- Frontend unit tests for API client success/error handling and board state transitions.
- Component tests with mocked API responses for loading, failure, retry, and every mutation.
- Playwright tests that reload after each representative mutation and verify persistence.
- Run the combined container with a temporary database and exercise the complete browser flow.

### Success criteria

- The board displayed after login is loaded from SQLite through FastAPI.
- Changes remain after reload and are not lost when the browser is reopened.
- Browser and backend tests cover the authenticated end-to-end path.

## Part 8: OpenRouter connectivity

### Checklist

- [ ] Add a backend OpenRouter client with a small, explicit interface and environment-based configuration.
- [ ] Use the configured `openai/gpt-oss-120b` model and keep the API key server-side.
- [ ] Add a development-only connectivity route or test harness for a simple `2+2` prompt; do not expose the secret or raw request headers.
- [ ] Normalize provider errors, timeouts, and malformed responses into useful backend errors.
- [ ] Make network tests opt-in through an environment flag so the default test suite remains deterministic.

### Tests and checks

- `pytest` unit tests with a mocked HTTP client for request shape, model selection, success, timeout, provider error, and malformed response.
- Run the opt-in `2+2` connectivity check with `OPENROUTER_API_KEY` configured and record the result without storing the response as a fixture containing secrets.
- Confirm the frontend cannot access the OpenRouter key.

### Success criteria

- A configured local environment can complete the `2+2` call through the backend.
- Normal tests do not require a live provider or secret.
- Provider failures are surfaced without crashing the application or exposing credentials.

## Part 9: Structured AI board assistant

### Checklist

- [ ] Define a versioned structured response contract containing the assistant reply and an optional validated board update.
- [ ] Send the current board JSON, the user's question, and persisted conversation history on every assistant request.
- [ ] Constrain the model instructions to return only the structured response and to preserve board invariants.
- [ ] Validate the model response server-side before applying any board update.
- [ ] Save the user message and assistant response in one transaction with the optional board update, or roll back all related changes on failure.
- [ ] Bound conversation history sent to the model while retaining the complete persisted history for the UI and future policy decisions.
- [ ] Add an authenticated assistant endpoint that returns the assistant message and the current board version/data.

### Tests and checks

- `pytest` tests for request composition, structured parsing, no-op responses, valid board updates, invalid updates, history limits, provider errors, and atomic rollback.
- Contract tests for representative card creation, edit, move, delete, and column rename instructions.
- Verify another user's board and conversation cannot appear in the request context.

### Success criteria

- Every assistant request includes the required board and conversation context.
- Only schema-valid model output can change persisted board state.
- Chat history and board changes remain consistent after success or failure.

## Part 10: AI chat sidebar

### Checklist

- [ ] Add a responsive sidebar widget integrated with the existing board visual language.
- [ ] Render persisted conversation history, a composer, submit state, provider/API errors, and a usable empty state.
- [ ] Send messages to the structured assistant endpoint and append the returned assistant message.
- [ ] Replace or refresh board state automatically when the response includes a board update.
- [ ] Prevent duplicate submissions and make keyboard and screen-reader interactions accessible.
- [ ] Keep the board usable on narrow screens by switching the sidebar to an appropriate mobile layout.

### Tests and checks

- Component tests for message rendering, submit/loading/error states, keyboard submission, and board refresh after an AI update.
- Playwright tests for a normal chat response, a card-changing response, persisted history after reload, failure recovery, logout, and desktop/mobile layouts.
- Run `npm run lint`, `npm run test:all`, backend `pytest`, and the production Docker smoke test.

### Success criteria

- An authenticated user can hold a persistent chat conversation beside the board.
- The assistant can create, edit, move, or delete cards and rename columns through validated structured output.
- The board visibly refreshes after an AI change and remains correct after a page reload.
- The complete application works from the single production container.

## Approval gates

- Part 1: user approval is required before application code changes.
- Part 5: user approval is required before implementing the persistent board schema.
- Part 8: live OpenRouter connectivity requires an explicitly configured key and opt-in test execution.