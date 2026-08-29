import json
import os
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.auth import connect_database
from app.board import BoardData, get_board, user_id_for_username

HISTORY_LIMIT = 20
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)


class AssistantResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(min_length=1)
    board: BoardData | None = None


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    role: str
    content: str
    board_updated: bool
    created_at: str


class AssistantProviderError(Exception):
    pass


@dataclass
class OpenRouterClient:
    api_key: str | None = None
    model: str = "openai/gpt-oss-120b"
    timeout: float = 30.0

    def complete(self, messages: list[dict[str, str]]) -> str:
        api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise AssistantProviderError("OpenRouter is not configured.")

        try:
            response = httpx.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "temperature": 0.1},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
            raise AssistantProviderError("OpenRouter returned an invalid response.") from error
        if not isinstance(content, str) or not content.strip():
            raise AssistantProviderError("OpenRouter returned an empty response.")
        return content


def assistant_messages(board: BoardData, history: list[ChatMessage], message: str) -> list[dict[str, str]]:
    system = """You are a project management assistant. Return JSON only with this exact shape:
{"reply":"short helpful response","board":null}
or with a complete board object in board when a change is requested.
The board must retain every column and card unless the user asks for a change. Preserve IDs,
put every card ID in exactly one column, and make card map keys equal card IDs. You can create,
edit, move, or delete cards and rename columns. Never include markdown fences or extra keys."""
    context = [{"role": "system", "content": system}]
    context.append({"role": "system", "content": f"Current board: {board.model_dump_json()}"})
    context.extend({"role": item.role, "content": item.content} for item in history[-HISTORY_LIMIT:])
    context.append({"role": "user", "content": message})
    return context


def parse_assistant_result(content: str) -> AssistantResult:
    try:
        parsed = json.loads(content)
        return AssistantResult.model_validate(parsed)
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise AssistantProviderError("Assistant returned an invalid structured response.") from error


def conversation_messages(username: str) -> list[ChatMessage]:
    user_id = user_id_for_username(username)
    with connect_database() as connection:
        rows = connection.execute(
            """
            SELECT messages.id, messages.role, messages.content,
                   messages.board_updated, messages.created_at
            FROM messages
            JOIN conversations ON conversations.id = messages.conversation_id
            WHERE conversations.user_id = ?
            ORDER BY messages.id
            """,
            (user_id,),
        ).fetchall()
    return [
        ChatMessage(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            board_updated=bool(row["board_updated"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]


def save_chat_turn(username: str, message: str, result: AssistantResult) -> list[ChatMessage]:
    user_id = user_id_for_username(username)
    with connect_database() as connection:
        now = "datetime('now')"
        conversation = connection.execute(
            "SELECT id FROM conversations WHERE user_id = ? ORDER BY id LIMIT 1", (user_id,)
        ).fetchone()
        if conversation is None:
            connection.execute(
                f"INSERT INTO conversations (user_id, created_at, updated_at) VALUES (?, {now}, {now})",
                (user_id,),
            )
            conversation_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            conversation_id = conversation["id"]

        connection.execute(
            f"INSERT INTO messages (conversation_id, role, content, board_updated, created_at) VALUES (?, 'user', ?, 0, {now})",
            (conversation_id, message),
        )
        if result.board is not None:
            connection.execute(
                """
                INSERT INTO boards (user_id, board_json, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    board_json = excluded.board_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, result.board.model_dump_json()),
            )
        connection.execute(
            f"INSERT INTO messages (conversation_id, role, content, board_updated, created_at) VALUES (?, 'assistant', ?, ?, {now})",
            (conversation_id, result.reply, int(result.board is not None)),
        )
        connection.execute(
            f"UPDATE conversations SET updated_at = {now} WHERE id = ?", (conversation_id,)
        )
    return conversation_messages(username)