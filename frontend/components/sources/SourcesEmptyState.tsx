interface SourcesEmptyStateProps {
  onImportClick?: () => void;
}

export default function SourcesEmptyState({
  onImportClick,
}: SourcesEmptyStateProps) {
  return (
    <div className="sources-empty-state">
      <div className="sources-empty-card">
        <div className="sources-empty-kicker">收藏夹资料</div>
        <div className="sources-empty-title">暂无收藏夹资料</div>
        <p>当前账号暂未读取到收藏夹，或收藏夹资料还没有完成同步。</p>
        {onImportClick && (
          <button
            type="button"
            className="sources-empty-action"
            onClick={onImportClick}
          >
            导入更多资料
          </button>
        )}
      </div>
    </div>
  );
}
