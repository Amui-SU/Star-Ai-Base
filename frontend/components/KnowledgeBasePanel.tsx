"use client";

import { useState, useEffect } from "react";
import { knowledgeBaseApi, type KnowledgeBase } from "@/lib/api";

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
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchKbs = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await knowledgeBaseApi.list();
        if (!cancelled) setKbs(data);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "加载知识库失败");
      }
      if (!cancelled) setLoading(false);
    };
    fetchKbs();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  useEffect(() => {
    if (!activeId) {
      onActiveKnowledgeBase?.(null);
      return;
    }
    onActiveKnowledgeBase?.(kbs.find((kb) => kb.id === activeId) ?? null);
  }, [activeId, kbs, onActiveKnowledgeBase]);

  const handleDelete = async (kb: KnowledgeBase) => {
    if (disabled) return;
    if (!window.confirm(`确定要删除知识库「${kb.name}」吗？此操作不可撤销。`))
      return;
    try {
      await knowledgeBaseApi.delete(kb.id);
      setKbs((prev) => prev.filter((k) => k.id !== kb.id));
      if (activeId === kb.id) onSelect(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  };

  const handleCreate = async () => {
    if (disabled) return;
    if (!newName.trim()) return;
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
      setLoading(true);
      try {
        const data = await knowledgeBaseApi.list();
        setKbs(data);
      } catch {}
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    }
  };

  const itemClass = (active: boolean) =>
    `w-full text-left px-3 py-2 rounded-xl text-xs font-medium transition-all duration-200 ${
      active
        ? "bg-(--paper-2) text-(--ink) ring-1 ring-(--border)"
        : "text-(--ink-soft) hover:bg-(--paper-2) active:scale-[0.98]"
    }`;

  const inputClass =
    "w-full px-2.5 py-1.5 rounded-lg border border-(--border) bg-(--input-bg) text-(--ink) text-xs placeholder:text-(--muted-weak) focus:outline-none focus:ring-2 focus:ring-(--accent)/25 focus:border-(--accent) transition-all duration-200";

  return (
    <div className="knowledge-panel px-3 py-3 border-b border-(--border)">
      <div className="knowledge-panel-head">
        <span className="knowledge-panel-label">当前知识库</span>
        <button
          onClick={() => {
            if (disabled) return;
            setCreating(!creating);
            setError(null);
          }}
          disabled={disabled}
          className={`text-[11px] font-semibold transition-colors duration-200 ${
            creating
              ? "text-(--danger)"
              : "text-(--muted) hover:text-(--ink-soft)"
          }`}
        >
          {creating ? "取消" : "+ 新建"}
        </button>
      </div>

      {creating && (
        <div className="mb-3 p-2.5 rounded-xl border border-(--border) bg-(--paper-2) space-y-2 animate-[fadeIn_200ms_ease-out]">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="知识库名称"
            className={inputClass}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <input
            type="text"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="描述（可选）"
            className={inputClass}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <button
            onClick={handleCreate}
            disabled={disabled || !newName.trim()}
            className="w-full py-1.5 rounded-lg bg-(--ink) text-white text-xs font-semibold hover:opacity-90 disabled:opacity-30 transition-opacity duration-200 active:scale-[0.98]"
          >
            创建知识库
          </button>
        </div>
      )}

      {error && (
        <div className="mb-2 text-[11px] text-(--danger) animate-[fadeIn_200ms_ease-out]">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-2">
          <div className="w-3.5 h-3.5 border-2 border-(--muted)/30 border-t-(--muted) rounded-full animate-spin" />
          <span className="text-xs text-(--muted)">加载中...</span>
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
        <div className="space-y-1 max-h-52 overflow-y-auto">
          {kbs.map((kb) => (
            <div key={kb.id} className="flex items-center gap-0.5">
              <button
                onClick={() => onSelect(kb)}
                disabled={disabled}
                className={`knowledge-item flex-1 ${itemClass(activeId === kb.id)}`}
                title={disabled ? "入库处理中，暂不能切换知识库" : kb.name}
              >
                <span className="flex items-center gap-2 truncate">
                  <span
                    className={`shrink-0 w-1.5 h-1.5 rounded-full transition-colors duration-200 ${
                      activeId === kb.id
                        ? "bg-(--accent)"
                        : "bg-(--muted) opacity-60"
                    }`}
                  />
                  <span className="truncate">{kb.name}</span>
                </span>
                {activeId === kb.id && (
                  <span className="knowledge-active-hint">用于当前聊天</span>
                )}
              </button>
              <button
                onClick={() => handleDelete(kb)}
                disabled={disabled}
                className="shrink-0 w-6 h-7 rounded-lg flex items-center justify-center text-[11px] text-(--muted) hover:text-(--danger) hover:bg-(--danger)/8 transition-colors"
                title="删除知识库"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
