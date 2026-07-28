"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { KnowledgeBasePanelView } from "@/components/knowledge-base/KnowledgeBasePanelView";
import { useRefreshVersion } from "@/hooks/refreshBus";
import { knowledgeBaseApi, type KnowledgeBase } from "@/lib/api";
import { displayKnowledgeBaseName } from "@/lib/displayNames";

interface Props {
  activeId: number | null;
  onSelect: (kb: KnowledgeBase | null) => void;
  onActiveKnowledgeBase?: (kb: KnowledgeBase | null) => void;
  disabled?: boolean;
}

export default function KnowledgeBasePanel({
  activeId,
  onSelect,
  onActiveKnowledgeBase,
  disabled = false,
}: Props) {
  const refreshVersion = useRefreshVersion("knowledge-bases");
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
  }, [refreshVersion]);

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
      <KnowledgeBasePanelView
        activeId={activeId}
        activeKbName={activeKbName}
        creating={creating}
        deleteTarget={deleteTarget}
        deletingId={deletingId}
        disabled={disabled}
        error={error}
        kbs={kbs}
        loading={loading}
        newDesc={newDesc}
        newName={newName}
        open={open}
        displayName={displayKnowledgeBaseName}
        onCancelDelete={() => setDeleteTarget(null)}
        onCreate={handleCreate}
        onDelete={handleDelete}
        onDeleteTarget={setDeleteTarget}
        onDescChange={setNewDesc}
        onNameChange={setNewName}
        onSelectKnowledgeBase={selectKnowledgeBase}
        onToggleCreate={() => {
          if (disabled) return;
          setCreating((next) => !next);
          setOpen(false);
          setDeleteTarget(null);
          setError(null);
        }}
        onToggleOpen={() => setOpen((next) => !next)}
      />
    </div>
  );
}
