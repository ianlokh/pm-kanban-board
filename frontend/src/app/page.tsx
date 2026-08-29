"use client";

import { useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { LoginForm } from "@/components/LoginForm";
import { ApiError, getBoard } from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

type User = {
  username: string;
};

type AuthState = "loading" | "signed-out" | "signed-in" | "error";

export default function Home() {
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [boardState, setBoardState] = useState<"loading" | "ready" | "error">("loading");

  const loadBoard = async () => {
    setBoardState("loading");
    try {
      setBoard(await getBoard());
      setBoardState("ready");
    } catch (boardError) {
      if (boardError instanceof ApiError && boardError.status === 401) {
        setUser(null);
        setAuthState("signed-out");
        return;
      }
      setBoardState("error");
    }
  };

  useEffect(() => {
    fetch("/api/auth/me", { credentials: "include" })
      .then((response) => {
        if (response.status === 401) {
          setAuthState("signed-out");
          return null;
        }
        if (!response.ok) {
          throw new Error("Unable to check authentication.");
        }
        return response.json() as Promise<User>;
      })
      .then((authenticatedUser) => {
        if (authenticatedUser) {
          setUser(authenticatedUser);
          setAuthState("signed-in");
          void loadBoard();
        }
      })
      .catch(() => setAuthState("error"));
  }, []);

  const handleLogout = async () => {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    setUser(null);
    setBoard(null);
    setAuthState("signed-out");
  };

  if (authState === "loading") {
    return <main className="flex min-h-screen items-center justify-center text-sm text-[var(--gray-text)]">Loading...</main>;
  }

  if (authState === "error") {
    return <main className="flex min-h-screen items-center justify-center px-6 text-sm text-red-700">Unable to connect to the server.</main>;
  }

  if (authState === "signed-out") {
    return <LoginForm onLogin={(authenticatedUser) => { setUser(authenticatedUser); setAuthState("signed-in"); void loadBoard(); }} />;
  }

  if (boardState === "loading") {
    return <main className="flex min-h-screen items-center justify-center text-sm text-[var(--gray-text)]">Loading your board...</main>;
  }

  if (boardState === "error" || !board) {
    return <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-sm text-red-700"><p>Unable to load your board.</p><button className="rounded-xl bg-[var(--purple-secondary)] px-4 py-2 font-semibold text-white" onClick={() => void loadBoard()} type="button">Retry</button></main>;
  }

  return (
    <>
      <div className="fixed right-6 top-6 z-10 flex items-center gap-3 rounded-full border border-[var(--stroke)] bg-white/90 px-4 py-2 text-sm shadow-[var(--shadow)] backdrop-blur">
        <span className="text-[var(--gray-text)]">{user?.username}</span>
        <button className="font-semibold text-[var(--purple-secondary)]" onClick={handleLogout} type="button">
          Log out
        </button>
      </div>
      <KanbanBoard initialBoard={board} onSessionExpired={() => { setBoard(null); setAuthState("signed-out"); }} />
    </>
  );
}
