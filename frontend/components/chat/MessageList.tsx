"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ThinkingProcess from "@/components/ThinkingProcess";
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
}

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
              {((m.sources && m.sources.length > 0) || m.webSearch) && (
                <details className="source-details">
                  <summary className="source-summary">
                    {(m.sources?.length ?? 0) > 0
                      ? `参考链接（${m.sources?.length ?? 0}）`
                      : "搜索状态"}
                  </summary>
                  <div className="source-list">
                    {m.sources?.map((s, i) => (
                      <a
                        key={i}
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="source-link"
                      >
                        <span className="source-type-badge">
                          {s.type === "web" ? "网页" : "知识库"}
                        </span>
                        <span className="source-link-title">{s.title}</span>
                      </a>
                    ))}
                    {m.webSearch?.message && (
                      <div className="web-search-block">
                        <div
                          className={`web-search-status ${m.webSearch.status}`}
                        >
                          {m.webSearch.message}
                        </div>
                        {(!m.webSearch.results ||
                          m.webSearch.results.length === 0) &&
                          m.webSearch.queries &&
                          m.webSearch.queries.length > 0 && (
                            <div className="web-search-details">
                              <div className="web-search-detail-label">
                                尝试查询
                              </div>
                              <div className="web-search-query-list">
                                {m.webSearch.queries.map((query) => (
                                  <span
                                    key={query}
                                    className="web-search-query"
                                  >
                                    {query}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        {m.webSearch.errors &&
                          m.webSearch.errors.length > 0 && (
                            <div className="web-search-details">
                              <div className="web-search-detail-label">
                                诊断信息
                              </div>
                              <div className="web-search-error-list">
                                {m.webSearch.errors.map((error, index) => (
                                  <span
                                    key={`${error.source || "web"}-${error.query || error.url || index}-${index}`}
                                    className="web-search-error"
                                  >
                                    {error.message}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                      </div>
                    )}
                  </div>
                </details>
              )}
              {m.role === "assistant" && m.content.trim() && (
                <div
                  className="message-actions"
                  role="group"
                  aria-label="回答操作"
                >
                  <button
                    type="button"
                    className={`message-action-btn ${copiedMessageId === m.id ? "active" : ""}`}
                    title="复制"
                    aria-label="复制"
                    onClick={() => onCopyMessage(m.id, m.content)}
                  >
                    <CopyIcon active={copiedMessageId === m.id} />
                  </button>
                  <button
                    type="button"
                    className={`message-action-btn soft-active ${
                      regeneratingMessageId === m.id ? "active spinning" : ""
                    }`}
                    title="重新生成"
                    aria-label="重新生成"
                    disabled={!!regeneratingMessageId}
                    onClick={() => {
                      let question = "";
                      for (let i = idx - 1; i >= 0; i -= 1) {
                        if (messages[i].role === "user") {
                          question = messages[i].content;
                          break;
                        }
                      }
                      onRegenerate(m.id, question);
                    }}
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
                      reactionMap[m.id] === "like" ? "active" : ""
                    }`}
                    title="点赞"
                    aria-label="点赞"
                    onClick={() => onReaction(m.id, "like")}
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
                    className={`message-action-btn ${
                      reactionMap[m.id] === "dislike" ? "active" : ""
                    }`}
                    title="点踩"
                    aria-label="点踩"
                    onClick={() => onReaction(m.id, "dislike")}
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
              )}
            </div>
            {m.role === "user" &&
              m.content.trim() &&
              editingMessageId !== m.id && (
                <div
                  className="message-actions user-message-actions"
                  role="group"
                  aria-label="问题操作"
                >
                  <button
                    type="button"
                    className={`message-action-btn ${copiedMessageId === m.id ? "active" : ""}`}
                    title="复制问题"
                    aria-label="复制问题"
                    onClick={() => onCopyMessage(m.id, m.content)}
                  >
                    <CopyIcon active={copiedMessageId === m.id} />
                  </button>
                  <button
                    type="button"
                    className="message-action-btn"
                    title="更改问题"
                    aria-label="更改问题"
                    onClick={() => onEditQuestion(m.id, m.content)}
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
              )}
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
