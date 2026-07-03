"use client";

import type {
  VideoNoteAiResponse,
  VideoNote,
  VideoNoteBlock,
  VideoNoteExportResponse,
  VideoNoteListItem,
  VideoNoteTemplateId,
  VideoNoteVideo,
} from "@/lib/api";
import type { VideoNoteSaveStatus } from "./useVideoNoteAutosave";
import VideoNoteAiPanel from "./VideoNoteAiPanel";
import VideoNoteDrawer from "./VideoNoteDrawer";
import VideoNoteHeader from "./VideoNoteHeader";
import VideoNoteListPanel, {
  type VideoNoteListFilter,
} from "./VideoNoteListPanel";
import VideoNoteMarkdownEditor from "./VideoNoteMarkdownEditor";
import VideoNoteTemplatePicker from "./VideoNoteTemplatePicker";
import VideoNoteToolRail from "./VideoNoteToolRail";

interface VideoNoteWorkspaceViewProps {
  fullscreen: boolean;
  noteChooserOpen: boolean;
  aiPanelCollapsed: boolean;
  visibleItems: VideoNoteListItem[];
  noteCounts: Record<VideoNoteListFilter, number>;
  listFilter: VideoNoteListFilter;
  listLoading: boolean;
  query: string;
  includeBodySearch: boolean;
  totalCount: number;
  selectedBvid: string | null;
  title: string;
  knowledgeBaseName?: string;
  saveStatus: VideoNoteSaveStatus;
  note: VideoNote | null;
  video: VideoNoteVideo | null;
  blocks: VideoNoteBlock[];
  creating: boolean;
  exported: VideoNoteExportResponse | null;
  exportFilenameTemplate: string;
  exporting: boolean;
  aiLoading: boolean;
  aiMessage: string | null;
  canUndoAiEdit: boolean;
  onClose?: () => void;
  onFilterChange: (filter: VideoNoteListFilter) => void;
  onQueryChange: (query: string) => void;
  onIncludeBodySearchChange: (include: boolean) => void;
  onCloseNoteChooser: () => void;
  onSelectVideo: (bvid: string) => void;
  onToggleNoteChooser: () => void;
  onTitleChange: (title: string) => void;
  onToggleFullscreen: () => void;
  onAddParagraph: () => void;
  onAddTodo: () => void;
  onExportMarkdown: () => Promise<VideoNoteExportResponse | null>;
  onExportFilenameTemplateChange: (value: string) => void;
  onToggleAiPanel: () => void;
  onCreateNote: (templateId: VideoNoteTemplateId) => void;
  onBlocksChange: (blocks: VideoNoteBlock[]) => void;
  onCollapseAiPanel: () => void;
  onGenerateSummary: () => Promise<VideoNoteAiResponse | void>;
  onGenerateQuestions: () => Promise<VideoNoteAiResponse | void>;
  onGenerateTimestamps: () => Promise<VideoNoteAiResponse | void>;
  onUndoAiEdit: () => void;
}

export default function VideoNoteWorkspaceView({
  fullscreen,
  noteChooserOpen,
  aiPanelCollapsed,
  visibleItems,
  noteCounts,
  listFilter,
  listLoading,
  query,
  includeBodySearch,
  totalCount,
  selectedBvid,
  title,
  knowledgeBaseName,
  saveStatus,
  note,
  video,
  blocks,
  creating,
  exported,
  exportFilenameTemplate,
  exporting,
  aiLoading,
  aiMessage,
  canUndoAiEdit,
  onClose,
  onFilterChange,
  onQueryChange,
  onIncludeBodySearchChange,
  onCloseNoteChooser,
  onSelectVideo,
  onToggleNoteChooser,
  onTitleChange,
  onToggleFullscreen,
  onAddParagraph,
  onAddTodo,
  onExportMarkdown,
  onExportFilenameTemplateChange,
  onToggleAiPanel,
  onCreateNote,
  onBlocksChange,
  onCollapseAiPanel,
  onGenerateSummary,
  onGenerateQuestions,
  onGenerateTimestamps,
  onUndoAiEdit,
}: VideoNoteWorkspaceViewProps) {
  return (
    <VideoNoteDrawer fullscreen={fullscreen} aiCollapsed={aiPanelCollapsed}>
      <section
        className={`video-note-workspace ${fullscreen ? "fullscreen" : "drawer"} ${
          noteChooserOpen ? "chooser-open" : "chooser-collapsed"
        } ${aiPanelCollapsed ? "ai-collapsed" : ""}`}
      >
        {noteChooserOpen && (
          <div
            className="video-note-chooser-menu"
            role="dialog"
            aria-label="选择笔记菜单"
          >
            <VideoNoteListPanel
              items={visibleItems}
              counts={noteCounts}
              filter={listFilter}
              loading={listLoading}
              query={query}
              includeBodySearch={includeBodySearch}
              totalCount={totalCount}
              selectedBvid={selectedBvid}
              onFilterChange={onFilterChange}
              onQueryChange={onQueryChange}
              onIncludeBodySearchChange={onIncludeBodySearchChange}
              onClose={onCloseNoteChooser}
              onSelectVideo={onSelectVideo}
            />
          </div>
        )}
        <main className="video-note-main">
          <VideoNoteHeader
            title={title || video?.title || "未命名笔记"}
            fullscreen={fullscreen}
            noteChooserOpen={noteChooserOpen}
            knowledgeBaseName={knowledgeBaseName}
            saveStatus={saveStatus}
            onClose={onClose}
            onToggleNoteChooser={onToggleNoteChooser}
            onTitleChange={onTitleChange}
            onToggleFullscreen={onToggleFullscreen}
          />
          {!selectedBvid ? (
            <div className="video-note-empty">选择一个视频开始记录</div>
          ) : note ? (
            <div className="video-note-editor-shell">
              <VideoNoteToolRail
                aiPanelCollapsed={aiPanelCollapsed}
                canExport={Boolean(note)}
                exported={exported}
                exportFilenameTemplate={exportFilenameTemplate}
                exporting={exporting}
                onAddParagraph={onAddParagraph}
                onAddTodo={onAddTodo}
                onExportMarkdown={onExportMarkdown}
                onExportFilenameTemplateChange={onExportFilenameTemplateChange}
                onToggleAiPanel={onToggleAiPanel}
              />
              <VideoNoteMarkdownEditor
                blocks={blocks}
                onChange={onBlocksChange}
              />
            </div>
          ) : video ? (
            <VideoNoteTemplatePicker
              video={video}
              creating={creating}
              onCreate={onCreateNote}
            />
          ) : (
            <div className="video-note-empty">加载视频信息...</div>
          )}
        </main>
        <aside
          className={`video-note-side-panel ${
            aiPanelCollapsed ? "collapsed" : ""
          }`}
        >
          <VideoNoteAiPanel
            collapsed={aiPanelCollapsed}
            loading={aiLoading}
            canUndoAiEdit={canUndoAiEdit}
            message={aiMessage}
            onCollapse={onCollapseAiPanel}
            onGenerateSummary={onGenerateSummary}
            onGenerateQuestions={onGenerateQuestions}
            onGenerateTimestamps={onGenerateTimestamps}
            onUndoAiEdit={onUndoAiEdit}
          />
        </aside>
      </section>
    </VideoNoteDrawer>
  );
}
