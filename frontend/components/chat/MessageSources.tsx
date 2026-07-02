"use client";

import type { Message } from "@/components/chat/types";

interface MessageSourcesProps {
  message: Message;
  onOpenVideoNote?: (bvid: string) => void;
}

export default function MessageSources({
  message,
  onOpenVideoNote,
}: MessageSourcesProps) {
  const sourceCount = message.sources?.length ?? 0;
  if (sourceCount === 0 && !message.webSearch) return null;

  return (
    <details className="source-details">
      <summary className="source-summary">
        {sourceCount > 0 ? `参考链接（${sourceCount}）` : "搜索状态"}
      </summary>
      <div className="source-list">
        {message.sources?.map((source, index) => (
          <div key={index} className="source-link-row">
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="source-link"
            >
              <span className="source-type-badge">
                {source.type === "web" ? "网页" : "知识库"}
              </span>
              <span className="source-link-title">{source.title}</span>
            </a>
            {source.bvid && source.type !== "web" && onOpenVideoNote && (
              <button
                type="button"
                className="source-note-action"
                onClick={() => onOpenVideoNote(source.bvid!)}
              >
                打开视频笔记 {source.title}
              </button>
            )}
          </div>
        ))}
        {message.webSearch?.message && (
          <div className="web-search-block">
            <div className={`web-search-status ${message.webSearch.status}`}>
              {message.webSearch.message}
            </div>
            {(!message.webSearch.results ||
              message.webSearch.results.length === 0) &&
              message.webSearch.queries &&
              message.webSearch.queries.length > 0 && (
                <div className="web-search-details">
                  <div className="web-search-detail-label">尝试查询</div>
                  <div className="web-search-query-list">
                    {message.webSearch.queries.map((query) => (
                      <span key={query} className="web-search-query">
                        {query}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            {message.webSearch.errors &&
              message.webSearch.errors.length > 0 && (
                <div className="web-search-details">
                  <div className="web-search-detail-label">诊断信息</div>
                  <div className="web-search-error-list">
                    {message.webSearch.errors.map((error, index) => (
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
  );
}
