import type { KnowledgeBase } from "@/lib/api";

import { KnowledgeBaseCreateCard } from "@/components/knowledge-base/KnowledgeBaseCreateCard";

interface KnowledgeBasePanelViewProps {
  activeId: number | null;
  activeKbName: string;
  creating: boolean;
  deleteTarget: KnowledgeBase | null;
  deletingId: number | null;
  disabled: boolean;
  error: string | null;
  kbs: KnowledgeBase[];
  loading: boolean;
  newDesc: string;
  newName: string;
  open: boolean;
  displayName: (name?: string | null) => string;
  onCancelDelete: () => void;
  onCreate: () => void;
  onDelete: () => void;
  onDeleteTarget: (kb: KnowledgeBase) => void;
  onDescChange: (value: string) => void;
  onNameChange: (value: string) => void;
  onSelectKnowledgeBase: (kb: KnowledgeBase) => void;
  onToggleCreate: () => void;
  onToggleOpen: () => void;
}

export function KnowledgeBasePanelView({
  activeId,
  activeKbName,
  creating,
  deleteTarget,
  deletingId,
  disabled,
  error,
  kbs,
  loading,
  newDesc,
  newName,
  open,
  displayName,
  onCancelDelete,
  onCreate,
  onDelete,
  onDeleteTarget,
  onDescChange,
  onNameChange,
  onSelectKnowledgeBase,
  onToggleCreate,
  onToggleOpen,
}: KnowledgeBasePanelViewProps) {
  return (
    <>
      <div className="knowledge-panel-head">
        <span className="knowledge-panel-label">当前知识库</span>
        <button
          type="button"
          onClick={onToggleCreate}
          disabled={disabled}
          className="knowledge-new-btn"
        >
          {creating ? "取消" : "+ 新建"}
        </button>
      </div>

      {creating && (
        <KnowledgeBaseCreateCard
          disabled={disabled}
          newName={newName}
          newDesc={newDesc}
          onNameChange={onNameChange}
          onDescChange={onDescChange}
          onCreate={onCreate}
        />
      )}

      {error && (
        <div className="knowledge-error" role="status">
          {error}
        </div>
      )}

      {loading ? (
        <div className="knowledge-loading">
          <span className="knowledge-loading-spinner" />
          <span>加载中...</span>
        </div>
      ) : kbs.length === 0 ? (
        <div>
          <div
            className="knowledge-item knowledge-empty-card"
            aria-disabled="true"
          >
            <div className="knowledge-empty-title">暂无知识库</div>
          </div>
          <div className="knowledge-empty-hint">点击「+ 新建」创建第一个</div>
        </div>
      ) : (
        <div className="knowledge-select">
          <button
            type="button"
            className="knowledge-select-trigger"
            disabled={disabled}
            onClick={onToggleOpen}
            aria-haspopup="listbox"
            aria-expanded={open}
          >
            <span className="knowledge-select-dot" aria-hidden="true" />
            <span className="knowledge-select-main">
              <span className="knowledge-select-name">{activeKbName}</span>
              <span className="knowledge-select-meta">
                {disabled ? "入库处理中，暂不可切换" : "用于当前聊天"}
              </span>
            </span>
            <span className="knowledge-select-caret" aria-hidden="true">
              ▾
            </span>
          </button>

          {open && (
            <div className="knowledge-select-popover" role="listbox">
              <div className="knowledge-option-list">
                {kbs.map((kb) => {
                  const active = activeId === kb.id;
                  const deleting = deletingId === kb.id;
                  const kbName = displayName(kb.name);
                  return (
                    <div
                      key={kb.id}
                      className={`knowledge-option-row ${active ? "active" : ""}`}
                    >
                      <button
                        type="button"
                        className="knowledge-option-btn"
                        onClick={() => onSelectKnowledgeBase(kb)}
                        disabled={disabled}
                        role="option"
                        aria-selected={active}
                        title={kbName}
                      >
                        <span className="knowledge-option-dot" />
                        <span className="knowledge-option-text">
                          <span className="knowledge-option-name">
                            {kbName}
                          </span>
                          <span className="knowledge-option-meta">
                            {active ? "当前聊天" : "切换到这个知识库"}
                          </span>
                        </span>
                      </button>
                      <button
                        type="button"
                        className="knowledge-delete-icon"
                        disabled={disabled || deleting}
                        onClick={() => onDeleteTarget(kb)}
                        title={`删除 ${kbName}`}
                        aria-label={`删除 ${kbName}`}
                      >
                        {deleting ? "..." : "×"}
                      </button>
                    </div>
                  );
                })}
              </div>

              {deleteTarget && (
                <div className="knowledge-delete-card">
                  <div>
                    <div className="knowledge-delete-title">
                      删除「{displayName(deleteTarget.name)}」？
                    </div>
                    <div className="knowledge-delete-copy">
                      会移除该知识库记录与入库索引，操作不可撤销。
                    </div>
                  </div>
                  <div className="knowledge-delete-actions">
                    <button
                      type="button"
                      className="knowledge-delete-cancel"
                      onClick={onCancelDelete}
                      disabled={deletingId !== null}
                    >
                      取消
                    </button>
                    <button
                      type="button"
                      className="knowledge-delete-confirm"
                      onClick={onDelete}
                      disabled={deletingId !== null}
                    >
                      {deletingId === deleteTarget.id ? "删除中" : "确认删除"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}
