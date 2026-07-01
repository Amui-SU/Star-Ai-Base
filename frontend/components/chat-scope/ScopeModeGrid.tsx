"use client";

interface ScopeModeGridProps {
  wholeKnowledgeBaseActive: boolean;
  onSelectWholeKnowledgeBase: () => void;
}

export default function ScopeModeGrid({
  wholeKnowledgeBaseActive,
  onSelectWholeKnowledgeBase,
}: ScopeModeGridProps) {
  return (
    <div className="scope-mode-grid" aria-label="范围类型">
      <button
        type="button"
        aria-label="整个知识库"
        className={`scope-mode-card ${wholeKnowledgeBaseActive ? "active" : ""}`}
        onClick={onSelectWholeKnowledgeBase}
      >
        <span className="scope-mode-icon">◎</span>
        <span>
          <span className="scope-mode-title">整个知识库</span>
          <span className="scope-mode-copy">默认检索全部已入库内容</span>
        </span>
      </button>
      <div className="scope-mode-card passive">
        <span className="scope-mode-icon">□</span>
        <span>
          <span className="scope-mode-title">收藏夹</span>
          <span className="scope-mode-copy">勾选一个或多个收藏夹</span>
        </span>
      </div>
      <div className="scope-mode-card passive">
        <span className="scope-mode-icon">◇</span>
        <span>
          <span className="scope-mode-title">单个视频</span>
          <span className="scope-mode-copy">搜索后精确加入问题范围</span>
        </span>
      </div>
    </div>
  );
}
