# Frontend Guide

## Current state

This directory contains the existing client-only Next.js Kanban demo. The app uses the App Router, TypeScript, React 19, and Tailwind CSS. The current home page renders `KanbanBoard` directly; authentication and backend persistence are not implemented yet.

## Structure

- `src/app/`: App Router entry points, layout, and global styles.
- `src/components/`: board, column, card, preview, and new-card UI components.
- `src/lib/kanban.ts`: `BoardData`, `Column`, and `Card` types, demo data, ID creation, and card movement logic.
- `src/**/*.test.ts` and `src/**/*.test.tsx`: Vitest and Testing Library unit/component tests.
- `tests/`: Playwright browser tests.
- `public/`: static frontend assets.

## Existing behavior

- The board starts from in-memory `initialData` and currently has five columns.
- Users can rename columns, add cards, delete cards, and drag cards between columns.
- `@dnd-kit` supplies drag-and-drop behavior.
- The current state is lost on refresh because there is no API or database integration.

## Commands

Run these from `frontend/`:

- `npm run dev`: start the Next.js development server.
- `npm run build`: create a production build.
- `npm run start`: serve the production build.
- `npm run lint`: run ESLint.
- `npm run test:unit`: run Vitest once.
- `npm run test:unit:watch`: run Vitest in watch mode.
- `npm run test:e2e`: run Playwright tests.
- `npm run test:all`: run unit tests followed by Playwright tests.

## Conventions for upcoming work

- Preserve the existing TypeScript types and component boundaries unless the backend contract requires a focused change.
- Keep API calls in a small typed client layer rather than scattering fetch logic through presentational components.
- Treat server responses as the source of truth once persistence is introduced; represent loading and request failures explicitly.
- Keep secrets and provider calls in the FastAPI backend. The frontend must never receive `OPENROUTER_API_KEY`.
- Add or update focused Vitest tests with component changes and Playwright coverage for user-visible workflows.
- Keep the static export compatible with FastAPI serving the production site at `/` and API routes at `/api`.