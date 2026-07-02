import type { BuildStatus, FolderStatus } from "@/lib/api";
import { getSourcesBuildButtonText } from "@/components/sources/sourcesPanelLogic";
import type { SourcesPanelFolder } from "@/components/sources/useSourcesPanelData";

interface SourcesPanelFooterProps {
  building: boolean;
  folders: SourcesPanelFolder[];
  knowledgeBaseId: number;
  message: string | null;
  organizeMessage: string | null;
  progress: BuildStatus | null;
  selected: Set<number>;
  selectedVideos: Set<string>;
  statusMap: Record<number, FolderStatus>;
  targetKnowledgeBase: string;
  onStartBuild: () => void;
}

export default function SourcesPanelFooter({
  building,
  folders,
  knowledgeBaseId,
  message,
  organizeMessage,
  progress,
  selected,
  selectedVideos,
  statusMap,
  targetKnowledgeBase,
  onStartBuild,
}: SourcesPanelFooterProps) {
  const hasSelection = selected.size > 0 || selectedVideos.size > 0;

  return (
    <div className="panel-footer">
      {progress && building && (
        <div className="mb-4">
          <div className="flex justify-between text-xs mb-2">
            <span className="text-(--muted) truncate">
              {progress.current_step}
            </span>
            <span className="text-(--accent)">{progress.progress}%</span>
          </div>
          <div className="progress">
            <div
              className="progress-bar"
              style={{ width: `${progress.progress}%` }}
            />
          </div>
        </div>
      )}

      {message && <div className="text-xs text-(--muted) mb-3">{message}</div>}
      {organizeMessage && (
        <div className="text-xs text-(--muted) mb-3">{organizeMessage}</div>
      )}

      <button
        onClick={onStartBuild}
        disabled={!hasSelection || building || !knowledgeBaseId}
        className={`sources-ingest-button ${
          hasSelection && knowledgeBaseId ? "active" : "idle"
        }`}
      >
        {knowledgeBaseId
          ? getSourcesBuildButtonText({
              building,
              progressStep: progress?.current_step,
              selectedCount: selected.size,
              selectedVideoCount: selectedVideos.size,
              selectedFolderIds: Array.from(selected),
              targetKnowledgeBase,
              folders,
              statusMap,
            })
          : "请先在侧栏创建知识库"}
      </button>

      {knowledgeBaseId ? (
        <p className="sources-ingest-hint">
          入库到 {targetKnowledgeBase} 后，可在右侧选择收藏夹或视频提问
        </p>
      ) : (
        <p className="sources-ingest-hint">创建知识库后即可将收藏夹内容入库</p>
      )}
    </div>
  );
}
