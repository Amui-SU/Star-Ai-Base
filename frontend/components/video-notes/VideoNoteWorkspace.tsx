"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  videoNoteApi,
  type VideoNote,
  type VideoNoteBlock,
  type VideoNoteExportResponse,
  type VideoNoteListItem,
  type VideoNoteTemplateId,
  type VideoNoteVideo,
} from "@/lib/api";
import { addVideoNoteBlock, createVideoNoteBlock } from "./videoNoteBlocks";
import { useVideoNoteAiEditing } from "./useVideoNoteAiEditing";
import { useVideoNoteAutosave } from "./useVideoNoteAutosave";
import VideoNoteWorkspaceView from "./VideoNoteWorkspaceView";

interface VideoNoteWorkspaceProps {
  knowledgeBaseId: number;
  knowledgeBaseName?: string;
  initialBvid?: string | null;
  initialMode?: "drawer" | "fullscreen";
  autosaveDelayMs?: number;
  onClose?: () => void;
}

type WorkspaceListFilter = "all" | "with_notes" | "without_notes";

function formatWorkspaceError(prefix: string, error: unknown) {
  const message = error instanceof Error ? error.message : "请稍后重试";
  return `${prefix}：${message}`;
}

export default function VideoNoteWorkspace({
  knowledgeBaseId,
  knowledgeBaseName,
  initialBvid = null,
  initialMode = "drawer",
  autosaveDelayMs = 800,
  onClose,
}: VideoNoteWorkspaceProps) {
  const [fullscreen, setFullscreen] = useState(initialMode === "fullscreen");
  const [noteChooserOpen, setNoteChooserOpen] = useState(false);
  const [items, setItems] = useState<VideoNoteListItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [includeBodySearch, setIncludeBodySearch] = useState(false);
  const [listFilter, setListFilter] = useState<WorkspaceListFilter>("all");
  const [selectedBvid, setSelectedBvid] = useState<string | null>(initialBvid);
  const [note, setNote] = useState<VideoNote | null>(null);
  const [video, setVideo] = useState<VideoNoteVideo | null>(null);
  const [title, setTitle] = useState("");
  const [blocks, setBlocks] = useState<VideoNoteBlock[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [exportFilenameTemplate, setExportFilenameTemplate] = useState("");
  const [creating, setCreating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState<VideoNoteExportResponse | null>(
    null,
  );
  const [aiLoading, setAiLoading] = useState(false);
  const [aiMessage, setAiMessage] = useState<string | null>(null);
  const [aiPanelCollapsed, setAiPanelCollapsed] = useState(false);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  const syncNoteState = useCallback((nextNote: VideoNote | null) => {
    setNote(nextNote);
    if (!nextNote) {
      setTitle("");
      setBlocks([]);
      setTags([]);
      setExportFilenameTemplate("");
      return;
    }
    setTitle(nextNote.title);
    setBlocks(nextNote.blocks);
    setTags(nextNote.tags);
    setExportFilenameTemplate(nextNote.export_filename_template ?? "");
  }, []);

  const loadList = useCallback(async () => {
    setListLoading(true);
    try {
      const response = await videoNoteApi.list({
        knowledgeBaseId,
        q: query || undefined,
        includeBodySearch,
      });
      setWorkspaceError(null);
      setItems(response.items);
      setSelectedBvid((current) => {
        if (current || response.items.length === 0) return current;
        const preferred =
          response.items.find((item) => item.has_note) ?? response.items[0];
        return preferred.bvid;
      });
    } catch (error) {
      setWorkspaceError(formatWorkspaceError("无法加载视频笔记列表", error));
    } finally {
      setListLoading(false);
    }
  }, [includeBodySearch, knowledgeBaseId, query]);

  const noteCounts = useMemo(
    () => ({
      all: items.length,
      with_notes: items.filter((item) => item.has_note).length,
      without_notes: items.filter((item) => !item.has_note).length,
    }),
    [items],
  );

  const visibleItems = useMemo(() => {
    if (listFilter === "with_notes") {
      return items.filter((item) => item.has_note);
    }
    if (listFilter === "without_notes") {
      return items.filter((item) => !item.has_note);
    }
    return items;
  }, [items, listFilter]);

  const loadDetail = useCallback(
    async (bvid: string) => {
      try {
        const detail = await videoNoteApi.detail(knowledgeBaseId, bvid);
        setWorkspaceError(null);
        setVideo(detail.video);
        syncNoteState(detail.note);
      } catch (error) {
        setVideo(null);
        syncNoteState(null);
        setWorkspaceError(formatWorkspaceError("无法加载视频信息", error));
      }
    },
    [knowledgeBaseId, syncNoteState],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadList();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadList]);

  useEffect(() => {
    if (!selectedBvid) return;
    const timer = window.setTimeout(() => {
      void loadDetail(selectedBvid);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadDetail, selectedBvid]);

  const saveState = useVideoNoteAutosave({
    note,
    title,
    blocks,
    tags,
    exportFilenameTemplate: exportFilenameTemplate.trim() || undefined,
    save: videoNoteApi.save,
    delayMs: autosaveDelayMs,
  });
  const aiEditing = useVideoNoteAiEditing({
    blocks,
    onBlocksChange: setBlocks,
  });
  const { resetAiEditing } = aiEditing;

  // AI 请求进行中切换视频时，用当前笔记 ID 判定并丢弃过期响应
  const noteIdRef = useRef<number | null>(null);
  useEffect(() => {
    noteIdRef.current = note?.id ?? null;
  }, [note]);

  const selectVideo = useCallback(
    (bvid: string) => {
      setSelectedBvid(bvid);
      setVideo(null);
      syncNoteState(null);
      setExported(null);
      setAiMessage(null);
      setWorkspaceError(null);
      setNoteChooserOpen(false);
      resetAiEditing();
    },
    [resetAiEditing, syncNoteState],
  );

  const createNote = async (templateId: VideoNoteTemplateId) => {
    if (!selectedBvid) return;
    setCreating(true);
    try {
      const created = await videoNoteApi.create({
        knowledge_base_id: knowledgeBaseId,
        bvid: selectedBvid,
        template_id: templateId,
      });
      syncNoteState(created);
      await loadList();
    } finally {
      setCreating(false);
    }
  };

  const exportMarkdown = async () => {
    if (!note) return null;
    setExporting(true);
    try {
      await saveState.flush();
      const response = await videoNoteApi.exportMarkdown(note.id);
      setExported(response);
      return response;
    } catch (error) {
      console.error("导出 Markdown 失败:", error);
      return null;
    } finally {
      setExporting(false);
    }
  };

  const generateSummary = async () => {
    if (!note) return;
    const requestNoteId = note.id;
    setAiLoading(true);
    setAiMessage("正在生成摘要...");
    try {
      const response = await videoNoteApi.generateSummary(note.id);
      if (noteIdRef.current !== requestNoteId) return;
      aiEditing.applyAiOperations(response.operations);
      setTags((current) =>
        Array.from(new Set([...current, ...response.tag_suggestions])),
      );
      setAiMessage(response.message);
      return response;
    } catch (error) {
      if (noteIdRef.current === requestNoteId) {
        setAiMessage("生成摘要失败，请检查网络连接或稍后重试");
      }
      console.error("生成摘要失败:", error);
    } finally {
      setAiLoading(false);
    }
  };

  const generateQuestions = async () => {
    if (!note) return;
    const requestNoteId = note.id;
    setAiLoading(true);
    setAiMessage("正在生成复盘问题...");
    try {
      const response = await videoNoteApi.aiEdit(note.id, {
        action: "generate_questions",
        instruction: null,
        selected_block_ids: [],
      });
      if (noteIdRef.current !== requestNoteId) return;
      aiEditing.applyAiOperations(response.operations);
      setAiMessage(response.message);
      return response;
    } catch (error) {
      if (noteIdRef.current === requestNoteId) {
        setAiMessage("生成问题失败，请检查网络连接或稍后重试");
      }
      console.error("生成问题失败:", error);
    } finally {
      setAiLoading(false);
    }
  };

  const generateTimestamps = async () => {
    if (!note) return;
    const requestNoteId = note.id;
    setAiLoading(true);
    setAiMessage("正在生成时间戳提纲...");
    try {
      const response = await videoNoteApi.aiEdit(note.id, {
        action: "generate_timestamps",
        instruction: null,
        selected_block_ids: [],
      });
      if (noteIdRef.current !== requestNoteId) return;
      aiEditing.applyAiOperations(response.operations);
      setAiMessage(response.message);
      return response;
    } catch (error) {
      if (noteIdRef.current === requestNoteId) {
        setAiMessage("生成时间戳失败，请检查网络连接或稍后重试");
      }
      console.error("生成时间戳失败:", error);
    } finally {
      setAiLoading(false);
    }
  };

  const addTodo = () => {
    setBlocks((current) =>
      addVideoNoteBlock(current, createVideoNoteBlock("todo")),
    );
  };
  const updateExportFilenameTemplate = (value: string) => {
    setExportFilenameTemplate(value);
    setExported(null);
  };

  return (
    <VideoNoteWorkspaceView
      fullscreen={fullscreen}
      noteChooserOpen={noteChooserOpen}
      aiPanelCollapsed={aiPanelCollapsed}
      visibleItems={visibleItems}
      noteCounts={noteCounts}
      listFilter={listFilter}
      listLoading={listLoading}
      query={query}
      includeBodySearch={includeBodySearch}
      totalCount={items.length}
      selectedBvid={selectedBvid}
      title={title}
      knowledgeBaseName={knowledgeBaseName}
      saveStatus={saveState.status}
      note={note}
      video={video}
      blocks={blocks}
      creating={creating}
      exported={exported}
      exportFilenameTemplate={exportFilenameTemplate}
      exporting={exporting}
      aiLoading={aiLoading}
      aiMessage={aiMessage}
      canUndoAiEdit={aiEditing.canUndoAiEdit}
      workspaceError={workspaceError}
      onClose={onClose}
      onFilterChange={setListFilter}
      onQueryChange={setQuery}
      onIncludeBodySearchChange={setIncludeBodySearch}
      onCloseNoteChooser={() => setNoteChooserOpen(false)}
      onSelectVideo={selectVideo}
      onToggleNoteChooser={() => setNoteChooserOpen((value) => !value)}
      onTitleChange={setTitle}
      onToggleFullscreen={() => setFullscreen((value) => !value)}
      onAddTodo={addTodo}
      onExportMarkdown={exportMarkdown}
      onExportFilenameTemplateChange={updateExportFilenameTemplate}
      onToggleAiPanel={() => setAiPanelCollapsed((value) => !value)}
      onCreateNote={createNote}
      onBlocksChange={setBlocks}
      onCollapseAiPanel={() => setAiPanelCollapsed(true)}
      onGenerateSummary={generateSummary}
      onGenerateQuestions={generateQuestions}
      onGenerateTimestamps={generateTimestamps}
      onUndoAiEdit={aiEditing.undoAiEdit}
    />
  );
}
