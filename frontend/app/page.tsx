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
import ImportModal from "@/components/ImportModal";
import SourcesPanel from "@/components/SourcesPanel";
import ChatPanel from "@/components/ChatPanel";
import { systemAuthApi, sourceBindingApi } from "@/lib/api";
import type { KnowledgeBase, SystemUser } from "@/lib/api";

export default function Home() {
  const MIN_SIDEBAR_WIDTH = 310;
  const [systemUser, setSystemUser] = useState<SystemUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [activeBindingId, setActiveBindingId] = useState<number | null>(null);
  const [activeKbId, setActiveKbId] = useState<number | null>(() => {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem("active_kb_id");
    return raw ? Number(raw) : null;
  });
  const [activeKnowledgeBase, setActiveKnowledgeBase] =
    useState<KnowledgeBase | null>(null);
  const [kbRefreshKey, setKbRefreshKey] = useState(0);
  const [showImport, setShowImport] = useState(false);
  const [statsKey, setStatsKey] = useState(0);
  const [knowledgeBuilding, setKnowledgeBuilding] = useState(false);

  // 主题
  const [isDarkMode, setIsDarkMode] = useState(() => {
    if (typeof window === "undefined") return true;
    const saved = localStorage.getItem("theme");
    return saved !== "light";
  });
  const [themeReady, setThemeReady] = useState(false);

  // 拖拽调整宽度
  const [leftWidth, setLeftWidth] = useState(() => {
    if (typeof window === "undefined") return 320;
    const raw = Number(localStorage.getItem("sidebar_width"));
    return Number.isFinite(raw) && raw >= MIN_SIDEBAR_WIDTH ? raw : 320;
  });
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("sidebar_open") !== "false";
  });
  const [isDragging, setIsDragging] = useState(false);

  // 主题初始化（默认深色）
  useEffect(() => {
    if (typeof window === "undefined") return;
    const t = window.setTimeout(() => setThemeReady(true), 0);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !themeReady) return;
    if (isDarkMode) {
      document.documentElement.classList.remove("light");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.add("light");
      localStorage.setItem("theme", "light");
    }
  }, [isDarkMode, themeReady]);

  // 检查系统登录态
  useEffect(() => {
    systemAuthApi
      .me()
      .then(async (user) => {
        setSystemUser(user);
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

  const toggleSidebar = useCallback(() => {
    setIsSidebarOpen((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        localStorage.setItem("sidebar_open", String(next));
      }
      return next;
    });
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

  const onAuthSuccess = (user: SystemUser) => {
    setSystemUser(user);
    setKbRefreshKey((v) => v + 1);
  };

  const onBiliBound = async () => {
    setShowImport(false);
    try {
      const bindings = await sourceBindingApi.list();
      const active = bindings.find((b) => b.status === "active");
      if (active) setActiveBindingId(active.id);
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
    setActiveKnowledgeBase(null);
  };

  const handleKnowledgeBaseSelect = useCallback((kb: KnowledgeBase | null) => {
    setActiveKnowledgeBase(kb);
    setActiveKbId(kb?.id ?? null);
    if (kb) {
      localStorage.setItem("active_kb_id", String(kb.id));
    } else {
      localStorage.removeItem("active_kb_id");
    }
  }, []);

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
        <section className="workspace-card relative" ref={containerRef}>
          <header className="workspace-topbar">
            <div className="workspace-brand">
              <span className="workspace-brand-mark">◇</span>
              <span>智库云</span>
            </div>
            <div className="workspace-top-actions">
              {themeReady && (
                <button
                  onClick={() => setIsDarkMode((p) => !p)}
                  className="workspace-icon-btn"
                  title={isDarkMode ? "切换到白天模式" : "切换到夜间模式"}
                >
                  {isDarkMode ? (
                    <svg
                      className="w-4 h-4"
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
                  ) : (
                    <svg
                      className="w-4 h-4"
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
                  )}
                </button>
              )}
              <UserMenu
                user={systemUser}
                onUserChange={setSystemUser}
                onLogout={onLogout}
              />
            </div>
          </header>

          <div className="workspace">
            {/* 侧边栏折叠按钮 */}
            <button
              onClick={toggleSidebar}
              className={`workspace-sidebar-toggle ${
                isSidebarOpen
                  ? "left-[calc(var(--sidebar-width)-16px)]"
                  : "left-1"
              }`}
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
                {
                  "--sidebar-width": `${sidebarWidth}px`,
                } as React.CSSProperties
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
                  onSelect={handleKnowledgeBaseSelect}
                  onActiveKnowledgeBase={setActiveKnowledgeBase}
                  refreshKey={kbRefreshKey}
                  disabled={knowledgeBuilding}
                />

                {/* 导入入口 */}
                {!activeBindingId && (
                  <div className="import-sidebar-entry">
                    <button
                      onClick={() => setShowImport(true)}
                      className="import-sidebar-btn"
                    >
                      + 导入
                    </button>
                    <p>选择 B 站收藏夹、视频 URL 或更多平台导入资料</p>
                  </div>
                )}
                {activeBindingId ? (
                  <SourcesPanel
                    sourceBindingId={activeBindingId}
                    knowledgeBaseId={activeKbId ?? 0}
                    knowledgeBaseName={activeKnowledgeBase?.name}
                    onImportClick={() => setShowImport(true)}
                    onBuildDone={() => setStatsKey((v) => v + 1)}
                    onBuildingChange={setKnowledgeBuilding}
                  />
                ) : (
                  <div className="flex-1 flex items-center justify-center p-6 text-center text-sm text-(--muted)">
                    点击「导入」选择资料来源
                  </div>
                )}
              </aside>
            </div>

            {/* 拖拽分隔条 */}
            <div
              className={`resizer transition-[width,opacity] duration-300 ${
                isSidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"
              }`}
              onMouseDown={handleMouseDown}
              style={{ cursor: "col-resize", width: isSidebarOpen ? 8 : 0 }}
            />

            <section
              className={`panel-chat-embedded ${isSidebarOpen ? "" : "full-width"}`}
              style={{ flex: 1 }}
            >
              <ChatPanel
                statsKey={statsKey}
                sidebarOpen={isSidebarOpen}
                sidebarWidth={sidebarWidth}
                knowledgeBaseId={activeKbId}
                knowledgeBaseName={activeKnowledgeBase?.name}
              />
            </section>
          </div>
        </section>
      </main>

      <ImportModal
        open={showImport}
        knowledgeBaseId={activeKbId}
        hasBilibiliBinding={!!activeBindingId}
        onClose={() => setShowImport(false)}
        onBound={onBiliBound}
        onImported={() => setStatsKey((v) => v + 1)}
      />
    </div>
  );
}
