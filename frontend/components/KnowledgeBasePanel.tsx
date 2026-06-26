"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { knowledgeBaseApi, type KnowledgeBase } from "@/lib/api";
import { displayKnowledgeBaseName } from "@/lib/displayNames";

interface Props {
  activeId: number | null;
  onSelect: (kb: KnowledgeBase | null) => void;
  onActiveKnowledgeBase?: (kb: KnowledgeBase | null) => void;
  refreshKey?: number;
  disabled?: boolean;
}

export default function KnowledgeBasePanel({
  activeId,
  onSelect,
  onActiveKnowledgeBase,
  refreshKey,
  disabled = false,
}: Props) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeBase | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const activeKb = useMemo(
    () => kbs.find((kb) => kb.id === activeId) ?? null,
    [activeId, kbs],
  );
  const activeKbName = activeKb
    ? displayKnowledgeBaseName(activeKb.name)
    : "选择知识库";

  useEffect(() => {
    let cancelled = false;
    const fetchKbs = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await knowledgeBaseApi.list();
        if (!cancelled) setKbs(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载知识库失败");
        }
      }
      if (!cancelled) setLoading(false);
    };
    fetchKbs();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  useEffect(() => {
    onActiveKnowledgeBase?.(activeKb);
  }, [activeKb, onActiveKnowledgeBase]);

  useEffect(() => {
    if (loading || activeId || kbs.length === 0) return;
    onSelect(kbs[0]);
  }, [activeId, kbs, loading, onSelect]);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setDeleteTarget(null);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        setDeleteTarget(null);
      }
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const handleCreate = async () => {
    if (disabled || !newName.trim()) return;
    try {
      setError(null);
      const created = await knowledgeBaseApi.create({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
      });
      setNewName("");
      setNewDesc("");
      setCreating(false);
      onSelect(created);
      const data = await knowledgeBaseApi.list();
      setKbs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    }
  };

  const handleDelete = async () => {
    if (disabled || !deleteTarget) return;
    const target = deleteTarget;
    try {
      setError(null);
      setDeletingId(target.id);
      await knowledgeBaseApi.delete(target.id);
      const nextKbs = kbs.filter((kb) => kb.id !== target.id);
      setKbs(nextKbs);
      setDeleteTarget(null);
      if (activeId === target.id) {
        onSelect(nextKbs[0] ?? null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeletingId(null);
    }
  };

  const selectKnowledgeBase = (kb: KnowledgeBase) => {
    if (disabled) return;
    onSelect(kb);
    setOpen(false);
    setDeleteTarget(null);
  };

  return (
    <div className="knowledge-panel" ref={rootRef}>
      <div className="knowledge-panel-head">
        <span className="knowledge-panel-label">当前知识库</span>
        <button
          type="button"
          onClick={() => {
            if (disabled) return;
            setCreating((next) => !next);
            setOpen(false);
            setDeleteTarget(null);
            setError(null);
          }}
          disabled={disabled}
          className="knowledge-new-btn"
        >
          {creating ? "取消" : "+ 新建"}
        </button>
      </div>

      {creating && (
        <div className="knowledge-create-card animate-[fadeIn_200ms_ease-out]">
          <div className="knowledge-create-head">
            <div>
              <div className="knowledge-create-title">新建知识库</div>
              <div className="knowledge-create-copy">
                为收藏夹资料准备一个独立的提问空间
              </div>
            </div>
          </div>
          <input
            type="text"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder="知识库名称"
            className="knowledge-create-input"
            onKeyDown={(event) => event.key === "Enter" && handleCreate()}
          />
          <input
            type="text"
            value={newDesc}
            onChange={(event) => setNewDesc(event.target.value)}
            placeholder="描述（可选）"
            className="knowledge-create-input"
            onKeyDown={(event) => event.key === "Enter" && handleCreate()}
          />
          <button
            type="button"
            onClick={handleCreate}
            disabled={disabled || !newName.trim()}
            className="knowledge-create-submit"
          >
            创建知识库
          </button>
        </div>
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
            onClick={() => setOpen((next) => !next)}
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
                  const kbName = displayKnowledgeBaseName(kb.name);
                  return (
                    <div
                      key={kb.id}
                      className={`knowledge-option-row ${active ? "active" : ""}`}
                    >
                      <button
                        type="button"
                        className="knowledge-option-btn"
                        onClick={() => selectKnowledgeBase(kb)}
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
                        onClick={() => setDeleteTarget(kb)}
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
                      删除「{displayKnowledgeBaseName(deleteTarget.name)}」？
                    </div>
                    <div className="knowledge-delete-copy">
                      会移除该知识库记录与入库索引，操作不可撤销。
                    </div>
                  </div>
                  <div className="knowledge-delete-actions">
                    <button
                      type="button"
                      className="knowledge-delete-cancel"
                      onClick={() => setDeleteTarget(null)}
                      disabled={deletingId !== null}
                    >
                      取消
                    </button>
                    <button
                      type="button"
                      className="knowledge-delete-confirm"
                      onClick={handleDelete}
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
    </div>
  );
}
