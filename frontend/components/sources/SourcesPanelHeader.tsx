import type { SourcesPanelFolder } from "@/components/sources/useSourcesPanelData";

interface SourcesPanelHeaderProps {
  folders: SourcesPanelFolder[];
  loading: boolean;
  organizeLoading: boolean;
  targetKnowledgeBase: string;
  onImportClick?: () => void;
  onOpenOrganizePreview: (folderId: number) => void | Promise<void>;
  onOrganizeMessage: (message: string) => void;
  onRefresh: () => void | Promise<void>;
}

export default function SourcesPanelHeader({
  folders,
  loading,
  organizeLoading,
  targetKnowledgeBase,
  onImportClick,
  onOpenOrganizePreview,
  onOrganizeMessage,
  onRefresh,
}: SourcesPanelHeaderProps) {
  const openDefaultFolderOrganize = () => {
    const defaultFolder = folders.find(
      (folder) => folder.is_default || folder.title === "默认收藏夹",
    );

    if (defaultFolder) {
      void onOpenOrganizePreview(defaultFolder.media_id);
      return;
    }

    onOrganizeMessage("未找到默认收藏夹");
  };

  return (
    <div className="sources-panel-head">
      <div className="sources-panel-head-top">
        <div className="sources-panel-title">收藏夹资料</div>
        <button
          type="button"
          className="sources-panel-action import-action"
          onClick={onImportClick}
        >
          + 导入
        </button>
      </div>
      <div className="sources-panel-head-bottom">
        <div className="sources-panel-subtitle">
          勾选后入库到{targetKnowledgeBase}
        </div>
        <div className="sources-panel-actions">
          <button
            onClick={openDefaultFolderOrganize}
            className="sources-panel-action"
            title="快速整理默认收藏夹"
            disabled={loading || organizeLoading}
          >
            {organizeLoading ? "整理中" : "整理"}
          </button>
          <button
            onClick={() => void onRefresh()}
            className="sources-panel-action"
            disabled={loading}
            title={loading ? "加载中..." : "刷新"}
            aria-label={loading ? "加载中..." : "刷新"}
          >
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
      </div>
    </div>
  );
}
