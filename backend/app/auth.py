import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, Request

SESSION_COOKIE = "pm_session"
SESSION_TTL = timedelta(days=7)


def database_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "data/app.db"))


def connect_database() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored_password: str) -> bool:
    try:
        salt_hex, digest_hex = stored_password.split(":", 1)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 120_000
        )
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def initialize_database() -> None:
    with connect_database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                board_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                board_updated INTEGER NOT NULL CHECK (board_updated IN (0, 1)),
                created_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            ("user", hash_password("password")),
        )


def create_session(user_id: int) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_TTL
    with connect_database() as connection:
        connection.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at.isoformat()),
        )
    return token, expires_at


def current_user(request: Request) -> dict[str, str]:
    initialize_database()
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    now = datetime.now(timezone.utc)
    with connect_database() as connection:
        row = connection.execute(
            """
            SELECT users.username, sessions.expires_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Authentication required")

        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at <= now:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
            raise HTTPException(status_code=401, detail="Authentication required")

    return {"username": row["username"]}


def authenticate(username: str, password: str) -> int | None:
    initialize_database()
    with connect_database() as connection:
        row = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return row["id"]


def delete_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with connect_database() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
