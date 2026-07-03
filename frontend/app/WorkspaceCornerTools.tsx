import type { SidebarMode } from "@/app/useWorkspaceState";

interface WorkspaceCornerToolsProps {
  onOpenSidebarMode: (mode: SidebarMode) => void;
  onOpenVideoNotes: () => void;
}

export default function WorkspaceCornerTools({
  onOpenSidebarMode,
  onOpenVideoNotes,
}: WorkspaceCornerToolsProps) {
  return (
    <div
      className="workspace-corner-tools"
      role="toolbar"
      aria-label="工作区快捷入口"
    >
      <button
        type="button"
        className="workspace-corner-tool"
        title="展开资料"
        aria-label="展开资料"
        onClick={() => onOpenSidebarMode("sources")}
      >
        <SourcesIcon />
      </button>
      <button
        type="button"
        className="workspace-corner-tool"
        title="对话历史"
        aria-label="打开对话历史"
        onClick={() => onOpenSidebarMode("history")}
      >
        <HistoryIcon />
      </button>
      <button
        type="button"
        className="workspace-corner-tool"
        title="笔记"
        aria-label="打开笔记"
        onClick={onOpenVideoNotes}
      >
        <NotesIcon />
      </button>
    </div>
  );
}

function SourcesIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <rect x="4" y="5" width="16" height="14" rx="3" strokeWidth="1.8" />
      <path d="M9 5v14" strokeWidth="1.8" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        d="M4 12a8 8 0 1 0 2.34-5.66"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M4 5.5v4h4"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 8v4l3 2"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function NotesIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path d="M6 4h9l3 3v13H6z" strokeWidth="1.8" strokeLinejoin="round" />
      <path
        d="M14 4v4h4M9 12h6M9 16h4"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
