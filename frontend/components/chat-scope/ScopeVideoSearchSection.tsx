"use client";

import ScopeVideoOption, {
  type ScopeVideoOptionItem,
} from "@/components/chat-scope/ScopeVideoOption";

interface ScopeVideoSearchSectionProps {
  query: string;
  videos: ScopeVideoOptionItem[];
  selectedBvids: readonly string[];
  onQueryChange: (query: string) => void;
  onToggleVideo: (bvid: string) => void;
}

export default function ScopeVideoSearchSection({
  query,
  videos,
  selectedBvids,
  onQueryChange,
  onToggleVideo,
}: ScopeVideoSearchSectionProps) {
  return (
    <div className="scope-section">
      <label className="scope-section-title" htmlFor="scope-video-search">
        单独选择视频
      </label>
      <input
        id="scope-video-search"
        className="scope-search-input"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="搜索视频标题或 BV 号"
        aria-label="搜索视频"
      />
      <div className="scope-video-list">
        {videos.length > 0 ? (
          videos.map((video) => (
            <ScopeVideoOption
              key={video.bvid}
              video={video}
              selected={selectedBvids.includes(video.bvid)}
              onToggleVideo={onToggleVideo}
            />
          ))
        ) : (
          <div className="scope-empty">没有匹配的视频</div>
        )}
      </div>
    </div>
  );
}
