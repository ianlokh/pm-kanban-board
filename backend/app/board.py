import secrets
from typing import Callable

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.auth import connect_database, initialize_database


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    details: str


class Column(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    cardIds: list[str]


class BoardData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[Column] = Field(min_length=1)
    cards: dict[str, Card]

    @model_validator(mode="after")
    def validate_references(self) -> "BoardData":
        column_ids = [column.id for column in self.columns]
        if len(column_ids) != len(set(column_ids)):
            raise ValueError("Column IDs must be unique")

        referenced_cards = [card_id for column in self.columns for card_id in column.cardIds]
        if len(referenced_cards) != len(set(referenced_cards)):
            raise ValueError("Each card must appear in only one column")
        if set(referenced_cards) != set(self.cards):
            raise ValueError("Every card must appear in exactly one column")
        if any(card.id != card_id for card_id, card in self.cards.items()):
            raise ValueError("Card map keys must match card IDs")
        return self


class ColumnRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)


class CardCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    details: str = ""


class CardUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    details: str


class CardMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_card_id: str = Field(min_length=1)
    over_id: str = Field(min_length=1)


INITIAL_BOARD = BoardData(
    columns=[
        {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
        {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
        {
            "id": "col-progress",
            "title": "In Progress",
            "cardIds": ["card-4", "card-5"],
        },
        {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
        {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
    ],
    cards={
        "card-1": {"id": "card-1", "title": "Align roadmap themes", "details": "Draft quarterly themes with impact statements and metrics."},
        "card-2": {"id": "card-2", "title": "Gather customer signals", "details": "Review support tags, sales notes, and churn feedback."},
        "card-3": {"id": "card-3", "title": "Prototype analytics view", "details": "Sketch initial dashboard layout and key drill-downs."},
        "card-4": {"id": "card-4", "title": "Refine status language", "details": "Standardize column labels and tone across the board."},
        "card-5": {"id": "card-5", "title": "Design card layout", "details": "Add hierarchy and spacing for scanning dense lists."},
        "card-6": {"id": "card-6", "title": "QA micro-interactions", "details": "Verify hover, focus, and loading states."},
        "card-7": {"id": "card-7", "title": "Ship marketing page", "details": "Final copy approved and asset pack delivered."},
        "card-8": {"id": "card-8", "title": "Close onboarding sprint", "details": "Document release notes and share internally."},
    },
)


def user_id_for_username(username: str) -> int:
    initialize_database()
    with connect_database() as connection:
        row = connection.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return int(row["id"])


def get_board(username: str) -> BoardData:
    user_id = user_id_for_username(username)
    with connect_database() as connection:
        row = connection.execute("SELECT board_json FROM boards WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            board = INITIAL_BOARD.model_copy(deep=True)
            connection.execute(
                "INSERT INTO boards (user_id, board_json, updated_at) VALUES (?, ?, datetime('now'))",
                (user_id, board.model_dump_json()),
            )
            return board
    return BoardData.model_validate_json(row["board_json"])


def save_board(username: str, board: BoardData) -> BoardData:
    user_id = user_id_for_username(username)
    with connect_database() as connection:
        connection.execute(
            """
            INSERT INTO boards (user_id, board_json, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                board_json = excluded.board_json,
                updated_at = excluded.updated_at
            """,
            (user_id, board.model_dump_json()),
        )
    return board


def update_board(username: str, updater: Callable[[BoardData], BoardData]) -> BoardData:
    user_id = user_id_for_username(username)
    with connect_database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT board_json FROM boards WHERE user_id = ?", (user_id,)
        ).fetchone()
        board = (
            INITIAL_BOARD.model_copy(deep=True)
            if row is None
            else BoardData.model_validate_json(row["board_json"])
        )
        next_board = updater(board)
        connection.execute(
            """
            INSERT INTO boards (user_id, board_json, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                board_json = excluded.board_json,
                updated_at = excluded.updated_at
            """,
            (user_id, next_board.model_dump_json()),
        )
    return next_board


def rename_column(board: BoardData, column_id: str, title: str) -> BoardData:
    if not any(column.id == column_id for column in board.columns):
        raise HTTPException(status_code=404, detail="Column not found")
    return board.model_copy(update={
        "columns": [
            column.model_copy(update={"title": title}) if column.id == column_id else column
            for column in board.columns
        ]
    })


def add_card(board: BoardData, payload: CardCreateRequest) -> BoardData:
    if not any(column.id == payload.column_id for column in board.columns):
        raise HTTPException(status_code=404, detail="Column not found")
    card_id = f"card-{secrets.token_urlsafe(8)}"
    card = Card(id=card_id, title=payload.title, details=payload.details)
    columns = [
        column.model_copy(update={"cardIds": [*column.cardIds, card_id]})
        if column.id == payload.column_id else column
        for column in board.columns
    ]
    return board.model_copy(update={"columns": columns, "cards": {**board.cards, card_id: card}})


def edit_card(board: BoardData, card_id: str, payload: CardUpdateRequest) -> BoardData:
    if card_id not in board.cards:
        raise HTTPException(status_code=404, detail="Card not found")
    cards = {**board.cards, card_id: board.cards[card_id].model_copy(update=payload.model_dump())}
    return board.model_copy(update={"cards": cards})


def delete_card(board: BoardData, card_id: str) -> BoardData:
    if card_id not in board.cards:
        raise HTTPException(status_code=404, detail="Card not found")
    cards = {key: card for key, card in board.cards.items() if key != card_id}
    columns = [
        column.model_copy(update={"cardIds": [value for value in column.cardIds if value != card_id]})
        for column in board.columns
    ]
    return board.model_copy(update={"cards": cards, "columns": columns})


def move_card(board: BoardData, payload: CardMoveRequest) -> BoardData:
    active_column = next((column for column in board.columns if payload.active_card_id in column.cardIds), None)
    over_column = next(
        (column for column in board.columns if column.id == payload.over_id or payload.over_id in column.cardIds),
        None,
    )
    if active_column is None or over_column is None:
        raise HTTPException(status_code=404, detail="Card or target not found")
    if active_column.id == over_column.id and payload.active_card_id == payload.over_id:
        return board

    next_columns = [column.model_copy(update={"cardIds": list(column.cardIds)}) for column in board.columns]
    active = next(column for column in next_columns if column.id == active_column.id)
    over = next(column for column in next_columns if column.id == over_column.id)
    active.cardIds.remove(payload.active_card_id)
    if payload.over_id == over.id:
        over.cardIds.append(payload.active_card_id)
    else:
        over_index = over.cardIds.index(payload.over_id)
        over.cardIds.insert(over_index, payload.active_card_id)
    return board.model_copy(update={"columns": next_columns})