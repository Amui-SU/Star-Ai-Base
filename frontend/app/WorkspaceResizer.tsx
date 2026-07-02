import type { CSSProperties, MouseEvent } from "react";

interface WorkspaceResizerProps {
  isSidebarOpen: boolean;
  onMouseDown: (event: MouseEvent) => void;
}

export default function WorkspaceResizer({
  isSidebarOpen,
  onMouseDown,
}: WorkspaceResizerProps) {
  return (
    <div
      className={`resizer transition-[width,opacity] duration-300 ${
        isSidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
      onMouseDown={onMouseDown}
      style={
        {
          cursor: "col-resize",
          width: isSidebarOpen ? 8 : 0,
        } satisfies CSSProperties
      }
    />
  );
}
