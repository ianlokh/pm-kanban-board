"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  getChatHistory,
  sendChatMessage,
  type ChatMessage,
} from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

type AssistantSidebarProps = {
  onBoardUpdate: (board: BoardData) => void;
  onSessionExpired: () => void;
};

export const AssistantSidebar = ({
  onBoardUpdate,
  onSessionExpired,
}: AssistantSidebarProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getChatHistory()
      .then(setMessages)
      .catch((historyError) => {
        if (historyError instanceof ApiError && historyError.status === 401) {
          onSessionExpired();
          return;
        }
        setError("Unable to load conversation history.");
      })
      .finally(() => setIsLoading(false));
  }, [onSessionExpired]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isSending) {
      return;
    }

    setError(null);
    setDraft("");
    setIsSending(true);
    const optimisticMessage: ChatMessage = {
      id: -Date.now(),
      role: "user",
      content: message,
      board_updated: false,
      created_at: new Date().toISOString(),
    };
    setMessages((previous) => [...previous, optimisticMessage]);

    try {
      const response = await sendChatMessage(message);
      setMessages((previous) => [...previous, response.message]);
      onBoardUpdate(response.board);
    } catch (sendError) {
      if (sendError instanceof ApiError && sendError.status === 401) {
        onSessionExpired();
        return;
      }
      setError(sendError instanceof Error ? sendError.message : "Unable to send message.");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <aside className="relative mx-6 mb-8 flex min-h-[520px] flex-col overflow-hidden rounded-[28px] border border-[var(--stroke)] bg-white/90 shadow-[var(--shadow)] backdrop-blur lg:fixed lg:bottom-6 lg:right-6 lg:top-24 lg:z-10 lg:mx-0 lg:mb-0 lg:w-[350px]">
      <header className="border-b border-[var(--stroke)] px-5 py-5">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">Workspace assistant</p>
        <h2 className="mt-2 font-display text-xl font-semibold text-[var(--navy-dark)]">Talk to your board</h2>
      </header>
      <div className="flex-1 space-y-3 overflow-y-auto p-5" aria-live="polite">
        {isLoading ? <p className="text-sm text-[var(--gray-text)]">Loading conversation...</p> : null}
        {!isLoading && messages.length === 0 ? <p className="text-sm leading-6 text-[var(--gray-text)]">Ask for a board summary or request a card change.</p> : null}
        {messages.map((message) => (
          <div key={message.id} className={message.role === "user" ? "ml-6 rounded-2xl bg-[var(--navy-dark)] px-4 py-3 text-sm leading-6 text-white" : "mr-6 rounded-2xl bg-[var(--surface)] px-4 py-3 text-sm leading-6 text-[var(--navy-dark)]"}>
            {message.content}
          </div>
        ))}
        {isSending ? <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--gray-text)]">Thinking...</p> : null}
      </div>
      <div className="border-t border-[var(--stroke)] p-4">
        {error ? <p className="mb-3 text-sm text-red-700" role="alert">{error}</p> : null}
        <form className="flex items-end gap-2" onSubmit={handleSubmit}>
          <textarea
            aria-label="Message the assistant"
            className="min-h-11 flex-1 resize-none rounded-xl border border-[var(--stroke)] bg-white px-3 py-3 text-sm text-[var(--navy-dark)] outline-none focus:border-[var(--primary-blue)]"
            disabled={isSending}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Ask about the board..."
            value={draft}
          />
          <button className="rounded-xl bg-[var(--secondary-purple)] px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50" disabled={isSending || !draft.trim()} type="submit">Send</button>
        </form>
      </div>
    </aside>
  );
};