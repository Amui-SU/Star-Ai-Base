"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  videoNoteApi,
  type VideoNote,
  type VideoNoteAiResponse,
  type VideoNoteAiResultSource,
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
import {
  getVideoNoteAiOverwriteTargets,
  type VideoNoteAiAction,
} from "./videoNoteAiUi";

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
  const [effectiveQuery, setEffectiveQuery] = useState("");
  const [includeBodySearch, setIncludeBodySearch] = useState(false);
  const [listFilter, setListFilter] = useState<WorkspaceListFilter>("all");
  const [selectedVideo, setSelectedVideo] = useState<{
    knowledgeBaseId: number;
    bvid: string;
  } | null>(initialBvid ? { knowledgeBaseId, bvid: initialBvid } : null);
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
  const [aiResultSource, setAiResultSource] =
    useState<VideoNoteAiResultSource | null>(null);
  const [pendingAiAction, setPendingAiAction] =
    useState<VideoNoteAiAction | null>(null);
  const [aiPanelCollapsed, setAiPanelCollapsed] = useState(false);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const listRequestIdRef = useRef(0);
  const detailRequestIdRef = useRef(0);
  const createRequestIdRef = useRef(0);
  const exportRequestIdRef = useRef(0);
  const activeSelectedBvid =
    selectedVideo?.knowledgeBaseId === knowledgeBaseId
      ? selectedVideo.bvid
      : null;

  useEffect(() => {
    const timer = window.setTimeout(() => setEffectiveQuery(query), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  const updateQuery = useCallback((nextQuery: string) => {
    listRequestIdRef.current += 1;
    setQuery(nextQuery);
  }, []);

  const updateIncludeBodySearch = useCallback((include: boolean) => {
    listRequestIdRef.current += 1;
    setIncludeBodySearch(include);
  }, []);

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
    const requestId = ++listRequestIdRef.current;
    setListLoading(true);
    try {
      const response = await videoNoteApi.list({
        knowledgeBaseId,
        q: effectiveQuery || undefined,
        includeBodySearch,
      });
      if (listRequestIdRef.current !== requestId) return;
      setWorkspaceError(null);
      setItems(response.items);
      setSelectedVideo((current) => {
        if (current?.knowledgeBaseId === knowledgeBaseId && current.bvid) {
          return current;
        }
        if (response.items.length === 0) {
          return null;
        }
        const preferred =
          response.items.find((item) => item.has_note) ?? response.items[0];
        return { knowledgeBaseId, bvid: preferred.bvid };
      });
    } catch (error) {
      if (listRequestIdRef.current !== requestId) return;
      setWorkspaceError(formatWorkspaceError("无法加载视频笔记列表", error));
    } finally {
      if (listRequestIdRef.current === requestId) setListLoading(false);
    }
  }, [effectiveQuery, includeBodySearch, knowledgeBaseId]);

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
      const requestId = ++detailRequestIdRef.current;
      try {
        const detail = await videoNoteApi.detail(knowledgeBaseId, bvid);
        if (detailRequestIdRef.current !== requestId) return;
        setWorkspaceError(null);
        setVideo(detail.video);
        syncNoteState(detail.note);
      } catch (error) {
        if (detailRequestIdRef.current !== requestId) return;
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
    return () => {
      window.clearTimeout(timer);
      listRequestIdRef.current += 1;
    };
  }, [loadList]);

  useEffect(() => {
    if (!activeSelectedBvid) return;
    const timer = window.setTimeout(() => {
      void loadDetail(activeSelectedBvid);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      detailRequestIdRef.current += 1;
    };
  }, [activeSelectedBvid, loadDetail]);

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
  const aiRequestIdRef = useRef(0);
  useEffect(() => {
    noteIdRef.current = note?.id ?? null;
  }, [note]);

  const resetSelectedVideoState = useCallback(() => {
    detailRequestIdRef.current += 1;
    createRequestIdRef.current += 1;
    exportRequestIdRef.current += 1;
    setSelectedVideo(null);
    setVideo(null);
    syncNoteState(null);
    setExported(null);
    setAiMessage(null);
    setAiResultSource(null);
    setPendingAiAction(null);
    setAiLoading(false);
    setCreating(false);
    setExporting(false);
    aiRequestIdRef.current += 1;
    setWorkspaceError(null);
    resetAiEditing();
  }, [resetAiEditing, syncNoteState]);

  const previousKnowledgeBaseIdRef = useRef(knowledgeBaseId);
  useLayoutEffect(() => {
    if (previousKnowledgeBaseIdRef.current === knowledgeBaseId) return;
    previousKnowledgeBaseIdRef.current = knowledgeBaseId;
    setItems([]);
    resetSelectedVideoState();
  }, [knowledgeBaseId, resetSelectedVideoState]);

  const selectVideo = useCallback(
    (bvid: string) => {
      resetSelectedVideoState();
      setSelectedVideo({ knowledgeBaseId, bvid });
      setNoteChooserOpen(false);
    },
    [knowledgeBaseId, resetSelectedVideoState],
  );

  const createNote = async (templateId: VideoNoteTemplateId) => {
    if (!activeSelectedBvid) return;
    const requestId = ++createRequestIdRef.current;
    setCreating(true);
    try {
      const created = await videoNoteApi.create({
        knowledge_base_id: knowledgeBaseId,
        bvid: activeSelectedBvid,
        template_id: templateId,
      });
      if (createRequestIdRef.current !== requestId) return;
      syncNoteState(created);
      if (createRequestIdRef.current !== requestId) return;
      await loadList();
    } finally {
      if (createRequestIdRef.current === requestId) setCreating(false);
    }
  };

  const exportMarkdown = async () => {
    if (!note) return null;
    const requestId = ++exportRequestIdRef.current;
    const requestNoteId = note.id;
    setExporting(true);
    try {
      await saveState.flush();
      if (exportRequestIdRef.current !== requestId) return null;
      const response = await videoNoteApi.exportMarkdown(requestNoteId);
      if (exportRequestIdRef.current !== requestId) return null;
      setExported(response);
      return response;
    } catch (error) {
      if (exportRequestIdRef.current === requestId) {
        console.error("导出 Markdown 失败:", error);
      }
      return null;
    } finally {
      if (exportRequestIdRef.current === requestId) setExporting(false);
    }
  };

  const dispatchAiAction = async (
    action: VideoNoteAiAction,
  ): Promise<VideoNoteAiResponse | void> => {
    if (!note) return;
    const requestNoteId = note.id;
    const requestId = ++aiRequestIdRef.current;
    const startingBlocks = blocks;
    setAiLoading(true);
    setAiResultSource(null);
    setAiMessage(
      action === "summary"
        ? "正在生成摘要..."
        : action === "questions"
          ? "正在生成复盘问题..."
          : "正在生成时间戳提纲...",
    );
    try {
      const response =
        action === "summary"
          ? await videoNoteApi.generateSummary(note.id)
          : await videoNoteApi.aiEdit(note.id, {
              action:
                action === "questions"
                  ? "generate_questions"
                  : "generate_timestamps",
              instruction: null,
              selected_block_ids: [],
            });
      if (
        noteIdRef.current !== requestNoteId ||
        aiRequestIdRef.current !== requestId
      )
        return;
      if (!aiEditing.applyAiOperations(response.operations, startingBlocks)) {
        setAiMessage("笔记内容已修改，请重新生成，已保留你的编辑。");
        return;
      }
      if (action === "summary") {
        setTags((current) =>
          Array.from(new Set([...current, ...response.tag_suggestions])),
        );
      }
      setAiMessage(response.message);
      setAiResultSource(response.result_source);
      return response;
    } catch (error) {
      if (
        noteIdRef.current === requestNoteId &&
        aiRequestIdRef.current === requestId
      ) {
        setAiMessage(
          `${action === "summary" ? "生成摘要" : action === "questions" ? "生成问题" : "生成时间戳"}失败，请检查网络连接或稍后重试`,
        );
      }
      console.error("AI 生成失败:", error);
    } finally {
      if (aiRequestIdRef.current === requestId) setAiLoading(false);
    }
  };

  const requestAiAction = (action: VideoNoteAiAction) => {
    const overwriteTargets = getVideoNoteAiOverwriteTargets(blocks, action);
    if (overwriteTargets.length > 0) {
      setPendingAiAction(action);
      return Promise.resolve();
    }
    return dispatchAiAction(action);
  };

  const aiOverwriteTargets = pendingAiAction
    ? getVideoNoteAiOverwriteTargets(blocks, pendingAiAction)
    : [];

  const confirmAiOverwrite = () => {
    const action = pendingAiAction;
    setPendingAiAction(null);
    if (action) void dispatchAiAction(action);
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
      selectedBvid={activeSelectedBvid}
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
      aiResultSource={aiResultSource}
      aiOverwriteTargets={aiOverwriteTargets}
      canUndoAiEdit={aiEditing.canUndoAiEdit}
      workspaceError={workspaceError}
      onClose={onClose}
      onFilterChange={setListFilter}
      onQueryChange={updateQuery}
      onIncludeBodySearchChange={updateIncludeBodySearch}
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
      onGenerateSummary={() => requestAiAction("summary")}
      onGenerateQuestions={() => requestAiAction("questions")}
      onGenerateTimestamps={() => requestAiAction("timestamps")}
      onUndoAiEdit={aiEditing.undoAiEdit}
      onCancelAiOverwrite={() => setPendingAiAction(null)}
      onConfirmAiOverwrite={confirmAiOverwrite}
    />
  );
}
