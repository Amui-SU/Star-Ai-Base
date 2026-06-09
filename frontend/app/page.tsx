"use client";

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type CSSProperties,
} from "react";
import AuthPage from "@/components/AuthPage";
import UserMenu from "@/components/UserMenu";
import KnowledgeBasePanel from "@/components/KnowledgeBasePanel";
import LoginModal from "@/components/LoginModal";
import SourcesPanel from "@/components/SourcesPanel";
import ChatPanel from "@/components/ChatPanel";
import { SystemUser, systemAuthApi, sourceBindingApi } from "@/lib/api";

export default function Home() {
  const MIN_SIDEBAR_WIDTH = 280;
  const [systemUser, setSystemUser] = useState<SystemUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [activeBindingId, setActiveBindingId] = useState<number | null>(null);
  const [activeKbId, setActiveKbId] = useState<number | null>(() => {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem("active_kb_id");
    return raw ? Number(raw) : null;
  });
  const [kbRefreshKey, setKbRefreshKey] = useState(0);
  const [showLogin, setShowLogin] = useState(false);
  const [statsKey, setStatsKey] = useState(0);
  const [selectedFolderIds, setSelectedFolderIds] = useState<number[]>([]);

  // 拖拽调整宽度
  const [leftWidth, setLeftWidth] = useState(320);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [themeReady, setThemeReady] = useState(false);

  // 检查系统登录态
  useEffect(() => {
    systemAuthApi
      .me()
      .then(async (user) => {
        setSystemUser(user);
        // 获取活跃的 B 站绑定
        try {
          const bindings = await sourceBindingApi.list();
          const active = bindings.find((b) => b.status === "active");
          if (active) setActiveBindingId(active.id);
        } catch {
          /* 绑定接口失败不影响登录 */
        }
      })
      .catch(() => setSystemUser(null))
      .finally(() => setAuthChecking(false));
  }, []);

  // 主题初始化
  useEffect(() => {
    if (typeof window === "undefined") return;
    const savedTheme = localStorage.getItem("theme");
    const prefersDark = window.matchMedia?.(
      "(prefers-color-scheme: dark)",
    ).matches;
    const nextDark =
      savedTheme === "dark" ||
      (savedTheme !== "light" &&
        (document.documentElement.classList.contains("dark") || !!prefersDark));
    const timer = window.setTimeout(() => {
      setIsDarkMode(nextDark);
      setThemeReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !themeReady) return;
    if (isDarkMode) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
      return;
    }
    document.documentElement.classList.remove("dark");
    localStorage.setItem("theme", "light");
  }, [isDarkMode, themeReady]);

  const toggleDarkMode = () => {
    setIsDarkMode((prev) => !prev);
  };
  const containerRef = useRef<HTMLElement>(null);
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = e.clientX - containerRect.left;
      const min = MIN_SIDEBAR_WIDTH;
      const max = containerRect.width * 0.5;
      setLeftWidth(Math.max(min, Math.min(max, newWidth)));
    },
    [isDragging, MIN_SIDEBAR_WIDTH],
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
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

  const onAuthSuccess = (user: SystemUser) => {
    setSystemUser(user);
    setKbRefreshKey((v) => v + 1);
  };

  const onBiliBound = async () => {
    setShowLogin(false);
    try {
      const bindings = await sourceBindingApi.list();
      console.log("绑定的账号列表:", bindings);
      const active = bindings.find((b) => b.status === "active");
      if (active) {
        console.log("活跃绑定 ID:", active.id);
        setActiveBindingId(active.id);
      } else {
        console.log("没有活跃的绑定");
      }
    } catch (e) {
      console.error("获取绑定列表失败:", e);
    }
  };

  const onLogout = () => {
    systemAuthApi.logout().catch(() => {});
    setSystemUser(null);
    localStorage.removeItem("bili_session");
    localStorage.removeItem("bili_user");
    localStorage.removeItem("bili_user_face");
    localStorage.removeItem("active_kb_id");
    setActiveKbId(null);
  };

  // 加载中
  if (authChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-(--bg)">
        <div className="w-8 h-8 border-2 border-(--accent) border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // 未登录 → 显示 AuthPage
  if (!systemUser) {
    return <AuthPage onAuthSuccess={onAuthSuccess} />;
  }

  // 已登录 → 工作台
  const sidebarWidth = Math.max(MIN_SIDEBAR_WIDTH, leftWidth);
  const sidebarHandleStyle: CSSProperties & Record<"--sidebar-width", string> =
    {
      "--sidebar-width": `${sidebarWidth}px`,
    };

  return (
    <div className="app-shell">
      <main className="app-main">
        <section className="workspace relative" ref={containerRef}>
          {/* 侧边栏折叠按钮 */}
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={`absolute top-4 z-10 w-8 h-8 flex items-center justify-center rounded-full shadow-md border border-(--border) bg-(--paper-2) text-(--ink-soft) hover:bg-(--paper-3) transition-all ${isSidebarOpen ? "left-[calc(var(--sidebar-width)-16px)]" : "left-4"}`}
            style={sidebarHandleStyle}
            title={isSidebarOpen ? "收起收藏夹" : "展开收藏夹"}
          >
            <svg
              className={`w-4 h-4 transition-transform ${isSidebarOpen ? "" : "rotate-180"}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>

          {/* 收藏夹侧栏 */}
          <div
            className={`sidebar-shell ${isSidebarOpen ? "open" : "closed"}`}
            style={
              { "--sidebar-width": `${sidebarWidth}px` } as React.CSSProperties
            }
          >
            <aside
              className="panel panel-sources"
              style={{
                width: sidebarWidth,
                opacity: isSidebarOpen ? 1 : 0,
                transform: isSidebarOpen
                  ? "translateX(0) scale(1)"
                  : "translateX(-14px) scale(0.985)",
                pointerEvents: isSidebarOpen ? "auto" : "none",
                transition:
                  "transform 340ms cubic-bezier(0.22,1,0.36,1), opacity 240ms ease",
              }}
            >
              {/* 知识库选择 */}
              <KnowledgeBasePanel
                activeId={activeKbId}
                onSelect={(id) => {
                  setActiveKbId(id);
                  localStorage.setItem(
                    "active_kb_id",
                    id === null ? "" : String(id),
                  );
                }}
                refreshKey={kbRefreshKey}
              />

              {/* B 站绑定状态 */}
              {!activeBindingId && (
                <div className="px-4 pt-4 pb-3 border-b border-(--border)">
                  <button
                    onClick={() => setShowLogin(true)}
                    className="w-full py-2 px-3 rounded-lg bg-(--paper-2) border border-(--border) text-sm text-(--accent-strong) hover:bg-(--paper-3) transition-colors font-medium"
                  >
                    绑定 B 站账号以导入收藏夹
                  </button>
                </div>
              )}
              {activeBindingId ? (
                <SourcesPanel
                  sourceBindingId={activeBindingId}
                  knowledgeBaseId={activeKbId ?? 0}
                  onBuildDone={() => setStatsKey((v) => v + 1)}
                  onSelectionChange={setSelectedFolderIds}
                />
              ) : (
                <div className="flex-1 flex items-center justify-center p-6 text-center text-sm text-(--muted)">
                  绑定 B 站账号后即可查看收藏夹并构建知识库
                </div>
              )}
            </aside>
          </div>

          {/* 拖拽分隔条 */}
          <div
            className={`resizer transition-[width,opacity] duration-300 ${isSidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"}`}
            onMouseDown={handleMouseDown}
            style={{ cursor: "col-resize", width: isSidebarOpen ? 8 : 0 }}
          />

          <section
            className={`panel-chat-embedded ${isSidebarOpen ? "" : "full-width"}`}
            style={{ flex: 1 }}
          >
            <ChatPanel
              statsKey={statsKey}
              folderIds={selectedFolderIds}
              sidebarOpen={isSidebarOpen}
              knowledgeBaseId={activeKbId}
            />
          </section>
        </section>
      </main>

      {/* 右上角用户菜单 */}
      <div className="fixed top-4 right-4 z-50 flex items-center gap-3">
        <UserMenu user={systemUser} onLogout={onLogout} />

        {/* 黑夜模式切换按钮 */}
        <button
          onClick={toggleDarkMode}
          className={`w-10 h-10 rounded-full flex items-center justify-center shadow-lg border transition-all ${
            isDarkMode
              ? "bg-gray-800 text-gray-200 border-(--border) hover:bg-gray-700"
              : "bg-[rgba(217,139,43,0.16)] text-[#8a5a22] border-[rgba(217,139,43,0.3)] hover:bg-[rgba(217,139,43,0.22)]"
          }`}
          title={isDarkMode ? "当前：黑夜模式" : "当前：白天模式"}
        >
          {isDarkMode ? (
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
              />
            </svg>
          ) : (
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
              />
            </svg>
          )}
        </button>
      </div>

      <LoginModal
        isOpen={showLogin}
        onClose={() => setShowLogin(false)}
        onBound={onBiliBound}
      />
    </div>
  );
}
