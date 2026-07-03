"use client";

import type { VideoNoteListItem } from "@/lib/api";

export type VideoNoteListFilter = "all" | "with_notes" | "without_notes";

interface VideoNoteListPanelProps {
  items: VideoNoteListItem[];
  counts: Record<VideoNoteListFilter, number>;
  filter: VideoNoteListFilter;
  loading: boolean;
  query: string;
  includeBodySearch: boolean;
  totalCount: number;
  selectedBvid: string | null;
  onFilterChange: (filter: VideoNoteListFilter) => void;
  onQueryChange: (query: string) => void;
  onIncludeBodySearchChange: (include: boolean) => void;
  onClose?: () => void;
  onSelectVideo: (bvid: string) => void;
}

const filterOptions: Array<{ id: VideoNoteListFilter; label: string }> = [
  { id: "all", label: "全部" },
  { id: "with_notes", label: "已有笔记" },
  { id: "without_notes", label: "未创建" },
];

export default function VideoNoteListPanel({
  items,
  counts,
  filter,
  loading,
  query,
  includeBodySearch,
  totalCount,
  selectedBvid,
  onFilterChange,
  onQueryChange,
  onIncludeBodySearchChange,
  onClose,
  onSelectVideo,
}: VideoNoteListPanelProps) {
  return (
    <aside className="video-note-list-panel">
      <div className="video-note-list-search">
        <div className="video-note-list-head">
          <div>
            <span className="video-note-kicker">选择笔记</span>
            <strong>{totalCount} 个视频</strong>
          </div>
          {onClose && (
            <button type="button" onClick={onClose} aria-label="关闭选择笔记">
              ×
            </button>
          )}
        </div>
        <input
          type="search"
          aria-label="搜索视频笔记"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索标题或标签"
        />
        <div className="video-note-list-filters" aria-label="笔记状态筛选">
          {filterOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              aria-pressed={filter === option.id}
              onClick={() => onFilterChange(option.id)}
            >
              {option.label} {counts[option.id]}
            </button>
          ))}
        </div>
        <label className="video-note-body-search">
          <input
            type="checkbox"
            checked={includeBodySearch}
            onChange={(event) =>
              onIncludeBodySearchChange(event.target.checked)
            }
          />
          搜索正文
        </label>
      </div>
      <div className="video-note-list">
        {loading ? (
          <div className="video-note-muted">加载中...</div>
        ) : items.length === 0 ? (
          <div className="video-note-muted">没有匹配的视频笔记</div>
        ) : (
          items.map((item) => {
            const active = item.bvid === selectedBvid;
            return (
              <button
                key={item.bvid}
                type="button"
                aria-pressed={active}
                className={`video-note-list-item ${active ? "active" : ""}`}
                onClick={() => onSelectVideo(item.bvid)}
              >
                <span className="video-note-list-title">
                  {item.display_title || item.title}
                </span>
                <span className="video-note-list-meta">
                  {item.folder_title ?? "未分组"}
                </span>
                <span
                  className={`video-note-list-status ${
                    item.has_note ? "ready" : "empty"
                  }`}
                >
                  {item.has_note ? "已创建" : "未创建"}
                </span>
                {active && (
                  <span className="video-note-current-badge">当前编辑</span>
                )}
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
