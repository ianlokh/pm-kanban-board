# Database Approach

SQLite is the MVP database. The application creates the configured database file and tables on first use. The default path is `backend/data/app.db`; set `DATABASE_PATH` to use another path in local development or tests. Docker Compose mounts the data directory as a named volume so container recreation does not discard application data.

The schema is defined in [database-schema.json](database-schema.json). Boards are stored as validated JSON in one row per user, matching the existing frontend `BoardData` shape. This keeps the first implementation small while preserving ordered columns and a card dictionary. The backend must enforce the semantic constraints listed in the JSON document because basic JSON Schema cannot express all cross-reference rules.

Chat history is normalized into `conversations` and `messages` rows. The complete history remains available to the UI, while each model request sends a bounded recent history selected by the backend. Board changes and the related assistant message will be committed together in a transaction.

Sessions contain opaque random tokens, user ownership, and an expiration timestamp. The browser receives only the token in an `HttpOnly`, `SameSite=Lax` cookie; passwords are stored as hashes.

## Versioning and operations

The `version` field in the JSON schema document identifies the persisted contract. Future changes should use a migration that creates or transforms the required SQLite columns and updates the document version. The MVP does not need a migration framework until the first schema change, but database initialization must be idempotent.

## Approval gate

This document and [database-schema.json](database-schema.json) are proposed for Part 5. Board and conversation tables should not be implemented until the user approves this model.