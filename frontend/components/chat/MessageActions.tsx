"use client";

import type { Message, Reaction } from "@/components/chat/types";

function CopyIcon({ active }: { active: boolean }) {
  if (active) {
    return (
      <svg
        className="w-3.5 h-3.5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 13l4 4L19 7"
        />
      </svg>
    );
  }

  return (
    <svg
      className="w-3.5 h-3.5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <rect
        x="9"
        y="9"
        width="13"
        height="13"
        rx="2"
        ry="2"
        strokeWidth={1.8}
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.8}
        d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
      />
    </svg>
  );
}

function findPreviousUserQuestion(messages: Message[], messageIndex: number) {
  for (let index = messageIndex - 1; index >= 0; index -= 1) {
    if (messages[index].role === "user") return messages[index].content;
  }
  return "";
}

interface AssistantMessageActionsProps {
  message: Message;
  messages: Message[];
  messageIndex: number;
  copiedMessageId: string | null;
  regeneratingMessageId: string | null;
  reaction: Reaction;
  onCopyMessage: (messageId: string, content: string) => void;
  onRegenerate: (assistantId: string, question: string) => void;
  onReaction: (messageId: string, reaction: Exclude<Reaction, null>) => void;
}

export function AssistantMessageActions({
  message,
  messages,
  messageIndex,
  copiedMessageId,
  regeneratingMessageId,
  reaction,
  onCopyMessage,
  onRegenerate,
  onReaction,
}: AssistantMessageActionsProps) {
  if (message.role !== "assistant" || !message.content.trim()) return null;

  return (
    <div className="message-actions" role="group" aria-label="回答操作">
      <button
        type="button"
        className={`message-action-btn ${copiedMessageId === message.id ? "active" : ""}`}
        title="复制"
        aria-label="复制"
        onClick={() => onCopyMessage(message.id, message.content)}
      >
        <CopyIcon active={copiedMessageId === message.id} />
      </button>
      <button
        type="button"
        className={`message-action-btn soft-active ${
          regeneratingMessageId === message.id ? "active spinning" : ""
        }`}
        title="重新生成"
        aria-label="重新生成"
        disabled={!!regeneratingMessageId}
        onClick={() =>
          onRegenerate(
            message.id,
            findPreviousUserQuestion(messages, messageIndex),
          )
        }
      >
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.9}
            d="M21 12a9 9 0 11-2.2-5.9l1.7 1.9h-3.1"
          />
        </svg>
      </button>
      <button
        type="button"
        className={`message-action-btn soft-active ${
          reaction === "like" ? "active" : ""
        }`}
        title="点赞"
        aria-label="点赞"
        onClick={() => onReaction(message.id, "like")}
      >
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M14 9V5a3 3 0 0 0-3-3l-1 5-3 3v9h11a3 3 0 0 0 3-3v-5a2 2 0 0 0-2-2h-5z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M7 10H4a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h3z"
          />
        </svg>
      </button>
      <button
        type="button"
        className={`message-action-btn ${reaction === "dislike" ? "active" : ""}`}
        title="点踩"
        aria-label="点踩"
        onClick={() => onReaction(message.id, "dislike")}
      >
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.9}
            d="M10 15v4a3 3 0 0 0 3 3l1-5 3-3V5H6a3 3 0 0 0-3 3v5a2 2 0 0 0 2 2h5z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.9}
            d="M17 14h3a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3z"
          />
        </svg>
      </button>
    </div>
  );
}

interface UserMessageActionsProps {
  message: Message;
  copiedMessageId: string | null;
  isEditing: boolean;
  onCopyMessage: (messageId: string, content: string) => void;
  onEditQuestion: (messageId: string, question: string) => void;
}

export function UserMessageActions({
  message,
  copiedMessageId,
  isEditing,
  onCopyMessage,
  onEditQuestion,
}: UserMessageActionsProps) {
  if (message.role !== "user" || !message.content.trim() || isEditing) {
    return null;
  }

  return (
    <div
      className="message-actions user-message-actions"
      role="group"
      aria-label="问题操作"
    >
      <button
        type="button"
        className={`message-action-btn ${copiedMessageId === message.id ? "active" : ""}`}
        title="复制问题"
        aria-label="复制问题"
        onClick={() => onCopyMessage(message.id, message.content)}
      >
        <CopyIcon active={copiedMessageId === message.id} />
      </button>
      <button
        type="button"
        className="message-action-btn"
        title="更改问题"
        aria-label="更改问题"
        onClick={() => onEditQuestion(message.id, message.content)}
      >
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15.232 5.232l3.536 3.536M9 11l6.768-6.768a2.5 2.5 0 013.536 0l.232.232a2.5 2.5 0 010 3.536L12.768 14.768A2 2 0 0111.354 15H9v-2.354A2 2 0 019.586 11.939zM5 19h14"
          />
        </svg>
      </button>
    </div>
  );
}
