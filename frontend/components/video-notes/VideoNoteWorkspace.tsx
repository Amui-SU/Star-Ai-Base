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
    exportFilenameTemplate: exportFilenameTemplate.trim() || undefined,
    save: videoNoteApi.save,
    delayMs: autosaveDelayMs,
  });
  const aiEditing = useVideoNoteAiEditing({
    blocks,
    onBlocksChange: setBlocks,
  });
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
    if (!note) return null;
    setExporting(true);
    try {
      await saveState.flush();
      const response = await videoNoteApi.exportMarkdown(note.id);
      setExported(response);
      return response;
    } finally {
      setExporting(false);
    }
  };

  const generateSummary = async () => {
    if (!note) return;
    setAiLoading(true);
    setAiMessage("正在生成摘要...");
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
    setAiMessage("正在生成复盘问题...");
    try {
      const response = await videoNoteApi.aiEdit(note.id, {
        action: "generate_questions",
        instruction: null,
        selected_block_ids: [],
      });
      aiEditing.applyAiOperations(response.operations);
      setAiMessage(response.message);
      return response;
    } finally {
      setAiLoading(false);
    }
  };

  const generateTimestamps = async () => {
    if (!note) return;
    setAiLoading(true);
    setAiMessage("正在生成时间戳提纲...");
    try {
      const response = await videoNoteApi.aiEdit(note.id, {
        action: "generate_timestamps",
        instruction: null,
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
      onClose={onClose}
      onFilterChange={setListFilter}
      onQueryChange={setQuery}
      onIncludeBodySearchChange={setIncludeBodySearch}
      onCloseNoteChooser={() => setNoteChooserOpen(false)}
      onSelectVideo={selectVideo}
      onToggleNoteChooser={() => setNoteChooserOpen((value) => !value)}
      onTitleChange={setTitle}
      onToggleFullscreen={() => setFullscreen((value) => !value)}
      onAddParagraph={addParagraph}
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
