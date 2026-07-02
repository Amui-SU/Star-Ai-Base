"use client";

import type { FolderStatus, Video } from "@/lib/api";
import { displayFolderTitle } from "@/lib/displayNames";
import {
  formatFolderSyncTime,
  getSourcesFolderStatus,
} from "@/components/sources/sourcesPanelLogic";
import type { SourcesPanelFolder } from "@/components/sources/useSourcesPanelData";

interface SourcesFolderListProps {
  editingVideoId: string | null;
  editingVideoName: string;
  folders: SourcesPanelFolder[];
  savingVideoId: string | null;
  selected: Set<number>;
  selectedVideos: Set<string>;
  statusMap: Record<number, FolderStatus>;
  getOriginalVideoTitle: (video: Video) => string;
  getVideoTitle: (video: Video) => string;
  onCancelVideoEdit: () => void;
  onPlayVideo: (video: { bvid: string; title: string }) => void;
  onRenameVideo: (video: Video) => void;
  onSaveVideoTitle: (video: Video, title: string) => void;
  onOpenVideoNote?: (bvid: string) => void;
  onToggleFolder: (folderId: number) => void;
  onToggleFolderSelect: (folderId: number) => void;
  onToggleVideoSelect: (folderId: number, bvid: string) => void;
  onVideoNameChange: (name: string) => void;
}

export default function SourcesFolderList({
  editingVideoId,
  editingVideoName,
  folders,
  savingVideoId,
  selected,
  selectedVideos,
  statusMap,
  getOriginalVideoTitle,
  getVideoTitle,
  onCancelVideoEdit,
  onPlayVideo,
  onRenameVideo,
  onSaveVideoTitle,
  onOpenVideoNote,
  onToggleFolder,
  onToggleFolderSelect,
  onToggleVideoSelect,
  onVideoNameChange,
}: SourcesFolderListProps) {
  return (
    <div className="sources-folder-list">
      {folders.map((folder) => {
        const status = getSourcesFolderStatus({
          folders,
          statusMap,
          mediaId: folder.media_id,
          totalInBilibili: folder.media_count,
        });
        const lastSync = formatFolderSyncTime(
          statusMap[folder.media_id]?.last_sync_at ?? undefined,
        );
        const folderTitle = displayFolderTitle(folder.title);

        return (
          <div
            key={folder.media_id}
            className={`folder-card ${
              selected.has(folder.media_id) ? "selected" : ""
            }`}
          >
            <div
              className="folder-head"
              onClick={() => onToggleFolder(folder.media_id)}
            >
              <input
                type="checkbox"
                checked={selected.has(folder.media_id)}
                onChange={() => onToggleFolderSelect(folder.media_id)}
                onClick={(event) => event.stopPropagation()}
                aria-label={`选择收藏夹 ${folderTitle}`}
                className="folder-checkbox"
              />
              <div className="folder-meta">
                <div className="folder-title" title={folderTitle}>
                  {folderTitle}
                </div>
                <div className="folder-count">
                  {status.indexedCount}/
                  {status.totalCount ?? folder.media_count} 个视频
                  {lastSync && ` · ${lastSync}`}
                </div>
              </div>
              <span className={`status-pill ${status.className}`}>
                {status.label}
              </span>
              <div className="folder-toggle">
                <svg
                  className={`w-4 h-4 transition-transform ${
                    folder.expanded ? "rotate-90" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </div>

            <div
              className={`folder-list-wrapper ${
                folder.expanded ? "expanded" : ""
              }`}
            >
              <div className="folder-list">
                {folder.loading ? (
                  <div className="text-xs text-(--muted)">加载中...</div>
                ) : folder.videos?.length === 0 ? (
                  <div className="text-xs text-(--muted)">暂无视频</div>
                ) : (
                  folder.videos?.map((video) => (
                    <SourcesVideoCard
                      key={video.bvid}
                      editingVideoId={editingVideoId}
                      editingVideoName={editingVideoName}
                      folderId={folder.media_id}
                      isFolderSelected={selected.has(folder.media_id)}
                      isSelected={selectedVideos.has(video.bvid)}
                      savingVideoId={savingVideoId}
                      video={video}
                      getOriginalVideoTitle={getOriginalVideoTitle}
                      getVideoTitle={getVideoTitle}
                      onCancelEdit={onCancelVideoEdit}
                      onNameChange={onVideoNameChange}
                      onPlay={onPlayVideo}
                      onRename={onRenameVideo}
                      onSaveTitle={onSaveVideoTitle}
                      onOpenVideoNote={onOpenVideoNote}
                      onToggleSelect={onToggleVideoSelect}
                    />
                  ))
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface SourcesVideoCardProps {
  editingVideoId: string | null;
  editingVideoName: string;
  folderId: number;
  isFolderSelected: boolean;
  isSelected: boolean;
  savingVideoId: string | null;
  video: Video;
  getOriginalVideoTitle: (video: Video) => string;
  getVideoTitle: (video: Video) => string;
  onCancelEdit: () => void;
  onNameChange: (name: string) => void;
  onPlay: (video: { bvid: string; title: string }) => void;
  onRename: (video: Video) => void;
  onSaveTitle: (video: Video, title: string) => void;
  onOpenVideoNote?: (bvid: string) => void;
  onToggleSelect: (folderId: number, bvid: string) => void;
}

function SourcesVideoCard({
  editingVideoId,
  editingVideoName,
  folderId,
  isFolderSelected,
  isSelected,
  savingVideoId,
  video,
  getOriginalVideoTitle,
  getVideoTitle,
  onCancelEdit,
  onNameChange,
  onPlay,
  onRename,
  onSaveTitle,
  onOpenVideoNote,
  onToggleSelect,
}: SourcesVideoCardProps) {
  const displayTitle = getVideoTitle(video);
  const originalTitle = getOriginalVideoTitle(video);
  const isEditing = editingVideoId === video.bvid;
  const isSaving = savingVideoId === video.bvid;

  return (
    <div className="video-card">
      <input
        type="checkbox"
        className="video-checkbox"
        checked={isFolderSelected || isSelected}
        onChange={() => onToggleSelect(folderId, video.bvid)}
        onClick={(event) => event.stopPropagation()}
        aria-label={`选择视频 ${displayTitle}`}
      />
      <button
        type="button"
        className="video-play-btn"
        onClick={() => onPlay({ bvid: video.bvid, title: displayTitle })}
        title="在线播放"
        aria-label={`播放 ${displayTitle}`}
      >
        ▶
      </button>
      <div className="video-card-body">
        {isEditing ? (
          <input
            className="video-title-input"
            value={editingVideoName}
            onChange={(event) => onNameChange(event.target.value)}
            autoFocus
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                onSaveTitle(video, editingVideoName);
              }
              if (event.key === "Escape") {
                onCancelEdit();
              }
            }}
          />
        ) : (
          <a
            href={`https://www.bilibili.com/video/${video.bvid}`}
            target="_blank"
            rel="noopener noreferrer"
            className="video-card-title truncate"
            aria-label={displayTitle}
          >
            {displayTitle}
          </a>
        )}
        <div className="video-card-meta">
          <span title={originalTitle}>{originalTitle}</span>
          {video.custom_title && video.custom_title !== originalTitle && (
            <span className="video-card-badge">自定义</span>
          )}
        </div>
      </div>
      <div className="video-card-actions">
        {isEditing ? (
          <>
            <button
              type="button"
              className="video-card-action primary"
              onClick={() => onSaveTitle(video, editingVideoName)}
              disabled={isSaving}
            >
              {isSaving ? "保存中" : "保存"}
            </button>
            <button
              type="button"
              className="video-card-action"
              onClick={onCancelEdit}
              disabled={isSaving}
            >
              取消
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="video-card-action"
              onClick={() => onRename(video)}
            >
              重命名
            </button>
            {onOpenVideoNote && (
              <button
                type="button"
                className="video-card-action"
                onClick={() => onOpenVideoNote(video.bvid)}
                aria-label={`打开视频笔记 ${displayTitle}`}
              >
                记笔记
              </button>
            )}
            {(video.custom_title || displayTitle !== originalTitle) && (
              <button
                type="button"
                className="video-card-action"
                onClick={() => onSaveTitle(video, originalTitle)}
              >
                恢复
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
