import type { CSSProperties } from "react";

interface WorkspaceSidebarToggleProps {
  style: CSSProperties;
  onCollapse: () => void;
}

export default function WorkspaceSidebarToggle({
  style,
  onCollapse,
}: WorkspaceSidebarToggleProps) {
  return (
    <button
      onClick={onCollapse}
      className="workspace-sidebar-toggle left-[calc(var(--sidebar-width)-16px)]"
      style={style}
      title="收起展开页"
      aria-label="收起展开页"
    >
      <svg
        className="sidebar-toggle-icon w-4 h-4 transition-transform"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M15 19l-7-7 7-7"
        />
      </svg>
    </button>
  );
}
