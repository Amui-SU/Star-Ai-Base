"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";

interface VideoNoteDrawerProps {
  children: ReactNode;
  fullscreen: boolean;
  aiCollapsed?: boolean;
}

const MIN_DRAWER_WIDTH = 420;
const DEFAULT_DRAWER_WIDTH = 720;
const DRAWER_WIDTH_STORAGE_KEY = "video_note_drawer_width";

const getStoredDrawerWidth = () => {
  if (typeof window === "undefined") return DEFAULT_DRAWER_WIDTH;
  const raw = Number(localStorage.getItem(DRAWER_WIDTH_STORAGE_KEY));
  return Number.isFinite(raw) && raw >= MIN_DRAWER_WIDTH
    ? raw
    : DEFAULT_DRAWER_WIDTH;
};

const clampDrawerWidth = (width: number, max: number) =>
  Math.max(MIN_DRAWER_WIDTH, Math.min(max, width));

export default function VideoNoteDrawer({
  children,
  fullscreen,
  aiCollapsed = false,
}: VideoNoteDrawerProps) {
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const [drawerWidth, setDrawerWidth] = useState(getStoredDrawerWidth);
  const [isDragging, setIsDragging] = useState(false);

  const persistDrawerWidth = useCallback((width: number) => {
    if (typeof window === "undefined") return;
    localStorage.setItem(DRAWER_WIDTH_STORAGE_KEY, String(Math.round(width)));
  }, []);

  const getMaxDrawerWidth = useCallback(() => {
    const parentWidth =
      drawerRef.current?.parentElement?.getBoundingClientRect().width ??
      window.innerWidth;
    return Math.max(MIN_DRAWER_WIDTH, Math.min(980, parentWidth * 0.72));
  }, []);

  const resizeToClientX = useCallback(
    (clientX: number) => {
      const drawer = drawerRef.current;
      if (!drawer) return;
      const parentLeft =
        drawer.parentElement?.getBoundingClientRect().left ??
        drawer.getBoundingClientRect().left;
      const nextWidth = clampDrawerWidth(
        clientX - parentLeft,
        getMaxDrawerWidth(),
      );
      setDrawerWidth(nextWidth);
      persistDrawerWidth(nextWidth);
    },
    [getMaxDrawerWidth, persistDrawerWidth],
  );

  const handleMouseDown = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      if (fullscreen) return;
      event.preventDefault();
      setIsDragging(true);
    },
    [fullscreen],
  );

  useEffect(() => {
    if (!isDragging) return;
    const handleMouseMove = (event: MouseEvent) => {
      resizeToClientX(event.clientX);
    };
    const handleMouseUp = () => {
      setIsDragging(false);
    };
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
    };
  }, [isDragging, resizeToClientX]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.style.setProperty(
      "--video-note-drawer-width",
      `${Math.round(drawerWidth)}px`,
    );
    return () => {
      document.documentElement.style.removeProperty(
        "--video-note-drawer-width",
      );
    };
  }, [drawerWidth]);

  const drawerStyle: CSSProperties &
    Record<"--video-note-drawer-width", string> = {
    "--video-note-drawer-width": `${Math.round(drawerWidth)}px`,
  };

  return (
    <div
      ref={drawerRef}
      className={`video-note-drawer ${fullscreen ? "fullscreen" : ""} ${
        aiCollapsed ? "ai-collapsed" : ""
      } ${isDragging ? "resizing" : ""}`}
      style={drawerStyle}
    >
      {children}
      {!fullscreen && (
        <div
          role="separator"
          aria-label="调整笔记宽度"
          aria-orientation="vertical"
          className="video-note-drawer-resizer"
          onMouseDown={handleMouseDown}
        />
      )}
    </div>
  );
}
