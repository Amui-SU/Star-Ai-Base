"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

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
import VideoNoteAiPanel from "./VideoNoteAiPanel";
import VideoNoteDrawer from "./VideoNoteDrawer";
import VideoNoteExportPanel from "./VideoNoteExportPanel";
import VideoNoteHeader from "./VideoNoteHeader";
import VideoNoteListPanel, {
  type VideoNoteListFilter,
} from "./VideoNoteListPanel";
import VideoNoteMarkdownEditor from "./VideoNoteMarkdownEditor";
import VideoNoteTemplatePicker from "./VideoNoteTemplatePicker";
import VideoNoteToolRail from "./VideoNoteToolRail";

interface VideoNoteWorkspaceProps {
  knowledgeBaseId: number;
  knowledgeBaseName?: string;
  initialBvid?: string | null;
  initialMode?: "drawer" | "fullscreen";
  autosaveDelayMs?: number;
  onClose?: () => void;
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
  const [noteChooserOpen, setNoteChooserOpen] = useState(
    initialMode === "fullscreen",
  );
  const [items, setItems] = useState<VideoNoteListItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [includeBodySearch, setIncludeBodySearch] = useState(false);
  const [listFilter, setListFilter] = useState<VideoNoteListFilter>("all");
  const [selectedBvid, setSelectedBvid] = useState<string | null>(initialBvid);
  const [note, setNote] = useState<VideoNote | null>(null);
  const [video, setVideo] = useState<VideoNoteVideo | null>(null);
  const [title, setTitle] = useState("");
  const [blocks, setBlocks] = useState<VideoNoteBlock[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState<VideoNoteExportResponse | null>(
    null,
  );
  const [aiLoading, setAiLoading] = useState(false);
  const [aiMessage, setAiMessage] = useState<string | null>(null);

  const syncNoteState = useCallback((nextNote: VideoNote | null) => {
    setNote(nextNote);
    if (!nextNote) {
      setTitle("");
      setBlocks([]);
      setTags([]);
      return;
    }
    setTitle(nextNote.title);
    setBlocks(nextNote.blocks);
    setTags(nextNote.tags);
  }, []);

  const loadList = useCallback(async () => {
    setListLoading(true);
    try {
      const response = await videoNoteApi.list({
        knowledgeBaseId,
        q: query || undefined,
        includeBodySearch,
      });
      setItems(response.items);
      setSelectedBvid((current) => {
        if (current || response.items.length === 0) return current;
        const preferred =
          response.items.find((item) => item.has_note) ?? response.items[0];
        return preferred.bvid;
      });
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
      const detail = await videoNoteApi.detail(knowledgeBaseId, bvid);
      setVideo(detail.video);
      syncNoteState(detail.note);
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
    exportFilenameTemplate: note?.export_filename_template,
    save: videoNoteApi.save,
    delayMs: autosaveDelayMs,
  });
  const aiEditing = useVideoNoteAiEditing({
    blocks,
    onBlocksChange: setBlocks,
  });
  const noteChooserVisible = fullscreen || noteChooserOpen;

  const selectVideo = useCallback(
    (bvid: string) => {
      setSelectedBvid(bvid);
      setVideo(null);
      syncNoteState(null);
      setExported(null);
      setAiMessage(null);
      setNoteChooserOpen(false);
    },
    [syncNoteState],
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
    if (!note) return;
    setExporting(true);
    try {
      setExported(await videoNoteApi.exportMarkdown(note.id));
    } finally {
      setExporting(false);
    }
  };

  const generateSummary = async () => {
    if (!note) return;
    setAiLoading(true);
    try {
      const response = await videoNoteApi.generateSummary(note.id);
      aiEditing.applyAiOperations(response.operations);
      setTags((current) =>
        Array.from(new Set([...current, ...response.tag_suggestions])),
      );
      setAiMessage(response.message);
      return response;
    } finally {
      setAiLoading(false);
    }
  };

  const generateQuestions = async () => {
    if (!note) return;
    setAiLoading(true);
    try {
      const response = await videoNoteApi.aiEdit(note.id, {
        action: "generate_questions",
        instruction: "生成复盘问题",
        selected_block_ids: [],
      });
      aiEditing.applyAiOperations(response.operations);
      setAiMessage(response.message);
      return response;
    } finally {
      setAiLoading(false);
    }
  };

  const addParagraph = () => {
    setBlocks((current) =>
      addVideoNoteBlock(current, createVideoNoteBlock("paragraph")),
    );
  };
  const addTodo = () => {
    setBlocks((current) =>
      addVideoNoteBlock(current, createVideoNoteBlock("todo")),
    );
  };

  return (
    <VideoNoteDrawer fullscreen={fullscreen}>
      <section
        className={`video-note-workspace ${fullscreen ? "fullscreen" : "drawer"} ${
          noteChooserVisible ? "chooser-open" : "chooser-collapsed"
        }`}
      >
        <VideoNoteListPanel
          items={visibleItems}
          counts={noteCounts}
          filter={listFilter}
          hidden={!noteChooserVisible}
          loading={listLoading}
          query={query}
          includeBodySearch={includeBodySearch}
          totalCount={items.length}
          selectedBvid={selectedBvid}
          onFilterChange={setListFilter}
          onQueryChange={setQuery}
          onIncludeBodySearchChange={setIncludeBodySearch}
          onSelectVideo={selectVideo}
        />
        <main className="video-note-main">
          <VideoNoteHeader
            title={title || video?.title || "未命名笔记"}
            fullscreen={fullscreen}
            noteChooserOpen={noteChooserVisible}
            knowledgeBaseName={knowledgeBaseName}
            saveStatus={saveState.status}
            onClose={onClose}
            onToggleNoteChooser={() => setNoteChooserOpen((value) => !value)}
            onTitleChange={setTitle}
            onToggleFullscreen={() => setFullscreen((value) => !value)}
          />
          {!selectedBvid ? (
            <div className="video-note-empty">选择一个视频开始记录</div>
          ) : note ? (
            <div className="video-note-editor-shell">
              <VideoNoteToolRail
                onAddParagraph={addParagraph}
                onAddTodo={addTodo}
              />
              <VideoNoteMarkdownEditor blocks={blocks} onChange={setBlocks} />
            </div>
          ) : video ? (
            <VideoNoteTemplatePicker
              video={video}
              creating={creating}
              onCreate={createNote}
            />
          ) : (
            <div className="video-note-empty">加载视频信息...</div>
          )}
        </main>
        <aside className="video-note-side-panel">
          <VideoNoteAiPanel
            loading={aiLoading}
            canUndoAiEdit={aiEditing.canUndoAiEdit}
            message={aiMessage}
            onGenerateSummary={generateSummary}
            onGenerateQuestions={generateQuestions}
            onUndoAiEdit={aiEditing.undoAiEdit}
          />
          <VideoNoteExportPanel
            exported={exported}
            exporting={exporting}
            onExportMarkdown={exportMarkdown}
          />
        </aside>
      </section>
    </VideoNoteDrawer>
  );
}
