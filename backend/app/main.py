from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import (
    SESSION_COOKIE,
    authenticate,
    create_session,
    current_user,
    delete_session,
)
from app.board import (
    BoardData,
    CardCreateRequest,
    CardMoveRequest,
    CardUpdateRequest,
    ColumnRenameRequest,
    add_card,
    delete_card,
    edit_card,
    get_board,
    move_card,
    rename_column,
    save_board,
    update_board,
)
from app.assistant import (
    AssistantProviderError,
    AssistantRequest,
    AssistantResult,
    ChatMessage,
    OpenRouterClient,
    assistant_messages,
    conversation_messages,
    get_board as get_assistant_board,
    parse_assistant_result,
    save_chat_turn,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Project Management MVP")
openrouter_client = OpenRouterClient()


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, str]:
    user_id = authenticate(payload.username, payload.password)
    if user_id is None:
        response.status_code = 401
        return {"detail": "Invalid username or password"}

    token, expires_at = create_session(user_id)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        expires=expires_at,
        httponly=True,
        samesite="lax",
    )
    return {"username": payload.username}


@app.get("/api/auth/me")
def me(user: dict[str, str] = Depends(current_user)) -> dict[str, str]:
    return user


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    delete_session(request)
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}


@app.get("/api/board", response_model=BoardData)
def read_board(user: dict[str, str] = Depends(current_user)) -> BoardData:
    return get_board(user["username"])


@app.put("/api/board", response_model=BoardData)
def replace_board(payload: BoardData, user: dict[str, str] = Depends(current_user)) -> BoardData:
    return save_board(user["username"], payload)


@app.patch("/api/board/columns/{column_id}", response_model=BoardData)
def rename_board_column(
    column_id: str,
    payload: ColumnRenameRequest,
    user: dict[str, str] = Depends(current_user),
) -> BoardData:
    return update_board(user["username"], lambda board: rename_column(board, column_id, payload.title))


@app.post("/api/board/cards", response_model=BoardData)
def create_board_card(
    payload: CardCreateRequest,
    user: dict[str, str] = Depends(current_user),
) -> BoardData:
    return update_board(user["username"], lambda board: add_card(board, payload))


@app.patch("/api/board/cards/{card_id}", response_model=BoardData)
def update_board_card(
    card_id: str,
    payload: CardUpdateRequest,
    user: dict[str, str] = Depends(current_user),
) -> BoardData:
    return update_board(user["username"], lambda board: edit_card(board, card_id, payload))


@app.delete("/api/board/cards/{card_id}", response_model=BoardData)
def remove_board_card(card_id: str, user: dict[str, str] = Depends(current_user)) -> BoardData:
    return update_board(user["username"], lambda board: delete_card(board, card_id))


@app.post("/api/board/move", response_model=BoardData)
def move_board_card(
    payload: CardMoveRequest,
    user: dict[str, str] = Depends(current_user),
) -> BoardData:
    return update_board(user["username"], lambda board: move_card(board, payload))


@app.get("/api/chat", response_model=list[ChatMessage])
def chat_history(user: dict[str, str] = Depends(current_user)) -> list[ChatMessage]:
    return conversation_messages(user["username"])


@app.post("/api/chat", response_model=dict[str, object])
def chat(
    payload: AssistantRequest,
    user: dict[str, str] = Depends(current_user),
) -> dict[str, object]:
    history = conversation_messages(user["username"])
    board = get_assistant_board(user["username"])
    try:
        content = openrouter_client.complete(assistant_messages(board, history, payload.message))
        result = parse_assistant_result(content)
        messages = save_chat_turn(user["username"], payload.message, result)
    except AssistantProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"message": messages[-1], "board": result.board or board}


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
