"use client";

import type { KnowledgeScopeFolder } from "@/lib/api";
import { displayFolderTitle } from "@/lib/displayNames";
import ScopeVideoOption from "@/components/chat-scope/ScopeVideoOption";

interface ScopeFolderSectionProps {
  folders: KnowledgeScopeFolder[];
  expandedFolderIds: ReadonlySet<number>;
  selectedFolderIds: readonly number[];
  selectedBvids: readonly string[];
  onToggleFolder: (mediaId: number) => void;
  onToggleExpanded: (mediaId: number) => void;
  onToggleVideo: (bvid: string) => void;
}

export default function ScopeFolderSection({
  folders,
  expandedFolderIds,
  selectedFolderIds,
  selectedBvids,
  onToggleFolder,
  onToggleExpanded,
  onToggleVideo,
}: ScopeFolderSectionProps) {
  return (
    <div className="scope-section">
      <div className="scope-section-title">收藏夹</div>
      {folders.length === 0 ? (
        <div className="scope-empty">当前知识库暂无可选范围</div>
      ) : (
        folders.map((folder) => {
          const isExpanded = expandedFolderIds.has(folder.media_id);
          const canExpand = folder.videos.length > 0;
          const folderTitle = displayFolderTitle(folder.title);
          return (
            <div key={folder.media_id} className="scope-folder">
              <div className="scope-folder-row">
                <label className="scope-option scope-folder-option">
                  <input
                    type="checkbox"
                    checked={selectedFolderIds.includes(folder.media_id)}
                    onChange={() => onToggleFolder(folder.media_id)}
                    aria-label={folderTitle}
                  />
                  <span className="min-w-0">
                    <span className="scope-option-title">{folderTitle}</span>
                    <span className="scope-option-subtitle">
                      {folder.video_count} 个已入库视频
                    </span>
                  </span>
                </label>
                <button
                  type="button"
                  className="scope-expand-btn"
                  disabled={!canExpand}
                  onClick={() => canExpand && onToggleExpanded(folder.media_id)}
                  aria-expanded={isExpanded}
                  aria-label={`${isExpanded ? "收起" : "展开"} ${folderTitle}`}
                >
                  ›
                </button>
              </div>
              {isExpanded && canExpand && (
                <div className="scope-folder-videos">
                  {folder.videos.map((video) => (
                    <ScopeVideoOption
                      key={video.bvid}
                      video={{ ...video, folderTitle }}
                      selected={selectedBvids.includes(video.bvid)}
                      onToggleVideo={onToggleVideo}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
