"use client";

import type { VideoNoteListItem } from "@/lib/api";

interface VideoNoteListPanelProps {
  items: VideoNoteListItem[];
  loading: boolean;
  query: string;
  includeBodySearch: boolean;
  selectedBvid: string | null;
  onQueryChange: (query: string) => void;
  onIncludeBodySearchChange: (include: boolean) => void;
  onSelectVideo: (bvid: string) => void;
}

export default function VideoNoteListPanel({
  items,
  loading,
  query,
  includeBodySearch,
  selectedBvid,
  onQueryChange,
  onIncludeBodySearchChange,
  onSelectVideo,
}: VideoNoteListPanelProps) {
  return (
    <aside className="video-note-list-panel">
      <div className="video-note-list-search">
        <input
          aria-label="搜索视频笔记"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索标题或标签"
        />
        <label>
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
          <div className="video-note-muted">暂无视频笔记</div>
        ) : (
          items.map((item) => (
            <button
              key={item.bvid}
              type="button"
              className={item.bvid === selectedBvid ? "active" : ""}
              onClick={() => onSelectVideo(item.bvid)}
            >
              <span>{item.title}</span>
              <small>
                {item.folder_title ?? "未分组"} ·{" "}
                {item.has_note ? "已创建" : "未创建"}
              </small>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
