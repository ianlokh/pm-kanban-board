import type { BoardData } from "@/lib/kanban";

export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  board_updated: boolean;
  created_at: string;
};

export type ChatResponse = {
  message: ChatMessage;
  board: BoardData;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const request = async <T>(url: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options?.headers },
  });

  if (!response.ok) {
    let detail = "Unable to complete the request.";
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // Keep the generic error when the server does not return JSON.
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
};

export type User = {
  username: string;
};

export const login = (username: string, password: string) =>
  request<User>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const logout = () => request<{ status: string }>("/api/auth/logout", { method: "POST" });

export const me = () => request<User>("/api/auth/me");

export const getBoard = () => request<BoardData>("/api/board");

export const renameColumn = (columnId: string, title: string) =>
  request<BoardData>(`/api/board/columns/${encodeURIComponent(columnId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

export const createCard = (columnId: string, title: string, details: string) =>
  request<BoardData>("/api/board/cards", {
    method: "POST",
    body: JSON.stringify({ column_id: columnId, title, details }),
  });

export const updateCard = (cardId: string, title: string, details: string) =>
  request<BoardData>(`/api/board/cards/${encodeURIComponent(cardId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title, details }),
  });

export const deleteCard = (cardId: string) =>
  request<BoardData>(`/api/board/cards/${encodeURIComponent(cardId)}`, {
    method: "DELETE",
  });

export const moveCard = (activeCardId: string, overId: string) =>
  request<BoardData>("/api/board/move", {
    method: "POST",
    body: JSON.stringify({ active_card_id: activeCardId, over_id: overId }),
  });

export const getChatHistory = () => request<ChatMessage[]>("/api/chat");

export const sendChatMessage = (message: string) =>
  request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });