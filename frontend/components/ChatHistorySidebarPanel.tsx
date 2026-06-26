"use client";

import { useEffect, useMemo, useState } from "react";
import { chatHistoryApi, type ChatConversationSummary } from "@/lib/api";

interface Props {
  knowledgeBaseId?: number | null;
  refreshKey?: number;
  onOpenConversation: (conversationId: number) => void;
  onNewConversation: () => void;
  onCollapse?: () => void;
}

export default function ChatHistorySidebarPanel({
  knowledgeBaseId,
  refreshKey = 0,
  onOpenConversation,
  onNewConversation,
  onCollapse,
}: Props) {
  const [items, setItems] = useState<ChatConversationSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadConversations = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await chatHistoryApi.list(
          knowledgeBaseId ? { knowledge_base_id: knowledgeBaseId } : {},
        );
        if (!cancelled) {
          setItems(response.items);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载历史失败");
          setItems([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadConversations();

    return () => {
      cancelled = true;
    };
  }, [knowledgeBaseId, refreshKey]);

  const groupedItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const filtered = normalizedQuery
      ? items.filter((item) => {
          const marker = getScopeMarker(item, knowledgeBaseId).toLowerCase();
          return (
            item.title.toLowerCase().includes(normalizedQuery) ||
            marker.includes(normalizedQuery)
          );
        })
      : items;

    const buckets: Array<{
      key: string;
      label: string;
      items: ChatConversationSummary[];
    }> = [
      { key: "today", label: "今天", items: [] },
      { key: "yesterday", label: "昨天", items: [] },
      { key: "seven", label: "7 天内", items: [] },
      { key: "thirty", label: "30 天内", items: [] },
      { key: "older", label: "更早", items: [] },
    ];
    const bucketByKey = new Map(buckets.map((bucket) => [bucket.key, bucket]));

    [...filtered]
      .sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
      )
      .forEach((item) => {
        bucketByKey.get(getRecencyBucket(item.updated_at))?.items.push(item);
      });

    return buckets.filter((bucket) => bucket.items.length > 0);
  }, [items, knowledgeBaseId, query]);

  return (
    <div className="sidebar-tool-panel chat-history-sidebar-panel">
      <div className="sidebar-history-topbar">
        <button
          type="button"
          className="sidebar-history-new-chat"
          onClick={onNewConversation}
        >
          <svg
            className="sidebar-history-new-chat-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path d="M5 19h11.5" strokeWidth="1.8" strokeLinecap="round" />
            <path
              d="M6 15.5V7.8A2.8 2.8 0 0 1 8.8 5H15"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M10 16l1-4 6.7-6.7a1.8 1.8 0 0 1 2.5 2.5L13.5 14.5 10 16Z"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>开启新对话</span>
        </button>
        <div className="sidebar-history-actions">
          <button
            type="button"
            className="sidebar-history-search-toggle"
            aria-label="检索对话"
            aria-expanded={searchOpen}
            onClick={() => setSearchOpen((open) => !open)}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" strokeWidth="1.8" />
              <path
                d="M16.5 16.5 21 21"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
          {onCollapse && (
            <button
              type="button"
              className="sidebar-history-collapse"
              aria-label="收起展开页"
              onClick={onCollapse}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  d="M15 19l-7-7 7-7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                />
              </svg>
            </button>
          )}
        </div>
      </div>

      {searchOpen && (
        <input
          className="sidebar-history-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="检索对话"
          autoFocus
        />
      )}

      {error && <div className="sidebar-tool-error">{error}</div>}
      {loading && items.length === 0 ? (
        <div className="sidebar-tool-empty">加载中...</div>
      ) : groupedItems.length === 0 ? (
        <div className="sidebar-tool-empty">
          {query.trim() ? "没有匹配的对话" : "暂无历史"}
        </div>
      ) : (
        <div className="sidebar-history-list" aria-label="对话历史">
          {groupedItems.map((group) => (
            <section className="sidebar-history-group" key={group.key}>
              <h3>{group.label}</h3>
              {group.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="sidebar-history-item"
                  onClick={() => onOpenConversation(item.id)}
                >
                  <span className="sidebar-history-title">{item.title}</span>
                  <small className="sidebar-history-scope">
                    {getScopeMarker(item, knowledgeBaseId)}
                  </small>
                </button>
              ))}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function getRecencyBucket(updatedAt: string) {
  const date = new Date(updatedAt);
  const today = startOfDay(new Date());
  const itemDay = startOfDay(date);
  const diffDays = Math.floor(
    (today.getTime() - itemDay.getTime()) / 86_400_000,
  );

  if (diffDays <= 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays <= 7) return "seven";
  if (diffDays <= 30) return "thirty";
  return "older";
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function getScopeMarker(
  item: ChatConversationSummary,
  knowledgeBaseId?: number | null,
) {
  const scope = item.scope;
  if (item.web_search) return "联网";
  if ((scope?.bvids?.length ?? 0) > 0) return "视频范围";
  if ((scope?.folder_ids?.length ?? 0) > 0) return "文件夹范围";
  if (item.knowledge_base_id) {
    return item.knowledge_base_id === knowledgeBaseId
      ? "当前知识库"
      : `知识库 #${item.knowledge_base_id}`;
  }
  return "全局";
}
