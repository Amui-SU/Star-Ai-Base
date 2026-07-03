import type { Video } from "@/lib/api";

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

export default function SourcesVideoCard({
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
