"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
} from "react";

export type SidebarMode = "sources" | "history" | "notes";

const MIN_SIDEBAR_WIDTH = 310;

const isMobileViewport = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(max-width: 1024px)").matches;

const getInitialSidebarOpen = () => {
  if (typeof window === "undefined") return true;
  const saved = localStorage.getItem("sidebar_open");
  if (saved !== null) return saved === "true";
  return !isMobileViewport();
};

const getInitialSidebarWidth = () => {
  if (typeof window === "undefined") return 320;
  const raw = Number(localStorage.getItem("sidebar_width"));
  return Number.isFinite(raw) && raw >= MIN_SIDEBAR_WIDTH ? raw : 320;
};

export function useWorkspaceState() {
  const [leftWidth, setLeftWidth] = useState(getInitialSidebarWidth);
  const [isSidebarOpen, setIsSidebarOpen] = useState(getInitialSidebarOpen);
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("sources");
  const conversationOpenRequestKeyRef = useRef(0);
  const [conversationOpenRequest, setConversationOpenRequest] = useState<{
    id: number;
    key: number;
  } | null>(null);
  const [newConversationRequestKey, setNewConversationRequestKey] = useState(0);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLElement>(null);

  const handleMouseDown = useCallback((event: ReactMouseEvent) => {
    event.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback(
    (event: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = event.clientX - containerRect.left;
      const max = containerRect.width * 0.5;
      setLeftWidth(Math.max(MIN_SIDEBAR_WIDTH, Math.min(max, newWidth)));
    },
    [isDragging],
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const setSidebarOpen = useCallback((next: boolean) => {
    setIsSidebarOpen(next);
    if (typeof window !== "undefined") {
      localStorage.setItem("sidebar_open", String(next));
    }
  }, []);

  const openSidebarMode = useCallback(
    (mode: SidebarMode) => {
      setSidebarMode(mode);
      setSidebarOpen(true);
    },
    [setSidebarOpen],
  );

  const collapseSidebar = useCallback(() => {
    setSidebarOpen(false);
  }, [setSidebarOpen]);

  const requestOpenConversation = useCallback((conversationId: number) => {
    conversationOpenRequestKeyRef.current += 1;
    setConversationOpenRequest({
      id: conversationId,
      key: conversationOpenRequestKeyRef.current,
    });
  }, []);

  const requestNewConversation = useCallback(() => {
    setNewConversationRequestKey((key) => key + 1);
    setSidebarMode("history");
  }, []);

  const refreshHistory = useCallback(() => {
    setHistoryRefreshKey((key) => key + 1);
  }, []);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    } else {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  useEffect(() => {
    if (typeof window === "undefined" || isDragging) return;
    localStorage.setItem("sidebar_width", String(leftWidth));
  }, [isDragging, leftWidth]);

  const sidebarWidth = Math.max(MIN_SIDEBAR_WIDTH, leftWidth);
  const sidebarHandleStyle: CSSProperties & Record<"--sidebar-width", string> =
    {
      "--sidebar-width": `${sidebarWidth}px`,
    };
  const sidebarPanelStyle: CSSProperties = isMobileViewport()
    ? {}
    : {
        width: sidebarWidth,
        opacity: isSidebarOpen ? 1 : 0,
        transform: isSidebarOpen
          ? "translateX(0) scale(1)"
          : "translateX(-14px) scale(0.985)",
        pointerEvents: isSidebarOpen ? "auto" : "none",
        transition:
          "transform 340ms cubic-bezier(0.22,1,0.36,1), opacity 240ms ease",
      };

  return {
    containerRef,
    handleMouseDown,
    isSidebarOpen,
    sidebarMode,
    sidebarWidth,
    sidebarHandleStyle,
    sidebarPanelStyle,
    conversationOpenRequest,
    newConversationRequestKey,
    historyRefreshKey,
    openSidebarMode,
    collapseSidebar,
    requestOpenConversation,
    requestNewConversation,
    refreshHistory,
  };
}
