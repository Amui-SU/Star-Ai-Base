"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ThinkingProcess from "@/components/ThinkingProcess";
import {
  AssistantMessageActions,
  UserMessageActions,
} from "@/components/chat/MessageActions";
import MessageSources from "@/components/chat/MessageSources";
import MarkdownCode from "@/components/chat/MarkdownCode";
import type { Message, Reaction } from "@/components/chat/types";

interface MessageListProps {
  messages: Message[];
  copiedMessageId: string | null;
  regeneratingMessageId: string | null;
  editingMessageId: string | null;
  editingQuestion: string;
  reactionMap: Record<string, Reaction>;
  endRef: React.RefObject<HTMLDivElement | null>;
  onEditingQuestionChange: (value: string) => void;
  onSubmitEditedQuestion: (messageId: string) => void;
  onCancelEdit: () => void;
  onCopyMessage: (messageId: string, content: string) => void;
  onRegenerate: (assistantId: string, question: string) => void;
  onReaction: (messageId: string, reaction: Exclude<Reaction, null>) => void;
  onEditQuestion: (messageId: string, question: string) => void;
  onOpenVideoNote?: (bvid: string) => void;
}

export default function MessageList({
  messages,
  copiedMessageId,
  regeneratingMessageId,
  editingMessageId,
  editingQuestion,
  reactionMap,
  endRef,
  onEditingQuestionChange,
  onSubmitEditedQuestion,
  onCancelEdit,
  onCopyMessage,
  onRegenerate,
  onReaction,
  onEditQuestion,
  onOpenVideoNote,
}: MessageListProps) {
  return (
    <div className="chat-window">
      {messages.map((m, idx) => (
        <div key={m.id} className={`message ${m.role}`}>
          <div className="message-main">
            <div
              className={`message-bubble ${
                m.role === "user" && editingMessageId === m.id ? "editing" : ""
              }`}
            >
              {m.role === "assistant" && m.thinkingStartedAt && (
                <ThinkingProcess
                  key={m.thinkingStartedAt}
                  active={Boolean(m.thinkingActive)}
                  startedAt={m.thinkingStartedAt}
                  durationMs={m.thinkingDurationMs}
                  thinking={m.thinking}
                />
              )}
              {m.role === "assistant" && m.webSearchActive && (
                <div
                  className="web-search-live-status"
                  role="status"
                  aria-live="polite"
                >
                  <span className="web-search-live-dot" />
                  <span className="web-search-live-text">
                    {m.webSearchProgress || "正在联网搜索外部资料"}
                  </span>
                </div>
              )}
              {m.role === "user" && editingMessageId === m.id ? (
                <div className="inline-edit-wrap">
                  <textarea
                    value={editingQuestion}
                    onChange={(e) => onEditingQuestionChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        onSubmitEditedQuestion(m.id);
                      }
                    }}
                    className="inline-edit-input"
                    rows={3}
                    autoFocus
                    placeholder="修改你的问题..."
                  />
                  <div className="inline-edit-actions">
                    <button
                      type="button"
                      className="inline-edit-btn ghost"
                      onClick={onCancelEdit}
                    >
                      取消
                    </button>
                    <button
                      type="button"
                      className="inline-edit-btn primary"
                      onClick={() => onSubmitEditedQuestion(m.id)}
                      disabled={!editingQuestion.trim()}
                    >
                      发送
                    </button>
                  </div>
                </div>
              ) : (
                <ReactMarkdown
                  className="markdown"
                  remarkPlugins={[remarkGfm]}
                  components={{
                    pre: ({ children }) => <>{children}</>,
                    code: ({ className, children, ...props }) => (
                      <MarkdownCode
                        inline={!className?.startsWith("language-")}
                        className={className}
                        {...props}
                      >
                        {children}
                      </MarkdownCode>
                    ),
                  }}
                >
                  {m.content}
                </ReactMarkdown>
              )}
              <MessageSources message={m} onOpenVideoNote={onOpenVideoNote} />
              <AssistantMessageActions
                message={m}
                messages={messages}
                messageIndex={idx}
                copiedMessageId={copiedMessageId}
                regeneratingMessageId={regeneratingMessageId}
                reaction={reactionMap[m.id] ?? null}
                onCopyMessage={onCopyMessage}
                onRegenerate={onRegenerate}
                onReaction={onReaction}
              />
            </div>
            <UserMessageActions
              message={m}
              copiedMessageId={copiedMessageId}
              isEditing={editingMessageId === m.id}
              onCopyMessage={onCopyMessage}
              onEditQuestion={onEditQuestion}
            />
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
