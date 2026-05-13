"use client";

import Image from "next/image";
import { useState, useEffect, useRef, useCallback, type CSSProperties } from "react";
import LoginModal from "@/components/LoginModal";
import DemoFlowModal from "@/components/DemoFlowModal";
import SourcesPanel from "@/components/SourcesPanel";
import ChatPanel from "@/components/ChatPanel";
import { UserInfo, authApi } from "@/lib/api";

export default function Home() {
  const MIN_SIDEBAR_WIDTH = 280;
  const [session, setSession] = useState<string | null>(null);
  const [user, setUser] = useState<string | null>(null);
  const [userAvatar, setUserAvatar] = useState<string | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [showDemo, setShowDemo] = useState(false);
  const [statsKey, setStatsKey] = useState(0);
  const [selectedFolderIds, setSelectedFolderIds] = useState<number[]>([]);

  // 拖拽调整宽度
  const [leftWidth, setLeftWidth] = useState(320);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [themeReady, setThemeReady] = useState(false);

  const normalizeAvatarUrl = useCallback((url?: string | null) => {
    if (!url) return null;
    if (url.startsWith("//")) return `https:${url}`;
    if (url.startsWith("http://")) return url.replace("http://", "https://");
    return url;
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const savedTheme = localStorage.getItem("theme");
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
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

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const newWidth = e.clientX - containerRect.left;
    // 限制最小宽度，最大 50% 容器宽度
    const min = MIN_SIDEBAR_WIDTH;
    const max = containerRect.width * 0.5;
    setLeftWidth(Math.max(min, Math.min(max, newWidth)));
  }, [isDragging, MIN_SIDEBAR_WIDTH]);

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

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const s = localStorage.getItem("bili_session");
      const u = localStorage.getItem("bili_user");
      const f = localStorage.getItem("bili_user_face");
      if (s && u) {
        setSession(s);
        setUser(u);
        setUserAvatar(normalizeAvatarUrl(f));
        // 兼容历史登录：本地没有头像时，补拉会话用户信息
        if (!f) {
          authApi
            .getSession(s)
            .then((res) => {
              const face = res.user_info?.face || null;
              if (face) {
                const normalizedFace = normalizeAvatarUrl(face);
                setUserAvatar(normalizedFace);
                localStorage.setItem("bili_user_face", normalizedFace || "");
              }
            })
            .catch(() => {});
        }
      }
    }, 0);

    return () => window.clearTimeout(timer);
  }, [normalizeAvatarUrl]);

  const onLogin = (sid: string, info: UserInfo) => {
    setSession(sid);
    setUser(info.uname);
    const normalizedFace = normalizeAvatarUrl(info.face || null);
    setUserAvatar(normalizedFace);
    setShowLogin(false);
    localStorage.setItem("bili_session", sid);
    localStorage.setItem("bili_user", info.uname);
    localStorage.setItem("bili_user_face", normalizedFace || "");
  };

  const onLogout = () => {
    if (session) authApi.logout(session).catch(() => { });
    setSession(null);
    setUser(null);
    setUserAvatar(null);
    localStorage.removeItem("bili_session");
    localStorage.removeItem("bili_user");
    localStorage.removeItem("bili_user_face");
  };

  const sidebarWidth = Math.max(MIN_SIDEBAR_WIDTH, leftWidth);
  const sidebarHandleStyle: CSSProperties & Record<"--sidebar-width", string> = {
    "--sidebar-width": `${sidebarWidth}px`,
  };

  return (
    <div className="app-shell">
      <main className="app-main">
        {!session ? (
          <section className="hero">
            <div className="hero-content">
              <span className="hero-kicker">让你的B站收藏夹不再吃灰</span>
              <h1 className="hero-title">把&quot;收藏&quot;变成真正可用的知识</h1>
              <p className="hero-desc">
                很多人收藏了大量学习视频，却迟迟没看、没整理、也找不到重点。<br />
                这里把碎片化内容接入 AI：自动提炼、语义检索、对话式回顾，让收藏真正提升效率。
              </p>

              <div className="hero-actions">
                <button className="btn btn-primary btn-lg" onClick={() => setShowLogin(true)}>
                  扫码登录开始构建
                </button>
                <button className="btn btn-outline" onClick={() => setShowDemo(true)}>
                  体验检索流程
                </button>
              </div>
            </div>

            <div className="hero-features">
              <div className="pipeline-row">
                {[
                  { icon: "1", title: "同步", desc: "接入收藏夹" },
                  { icon: "2", title: "提炼", desc: "整理要点" },
                  { icon: "3", title: "检索", desc: "语义查找" },
                  { icon: "4", title: "回顾", desc: "对话复习" },
                ].map((item, i) => (
                  <div key={i} className="pipeline-card">
                    <span className="pipeline-icon">{item.icon}</span>
                    <div className="pipeline-text">
                      <strong>{item.title}</strong>
                      <span>{item.desc}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        ) : (
          <section className="workspace relative" ref={containerRef}>
            {/* 侧边栏折叠按钮 */}
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className={`absolute top-4 z-10 w-8 h-8 flex items-center justify-center rounded-full shadow-md border border-(--border) bg-(--paper-2) text-(--ink-soft) hover:bg-(--paper-3) transition-all ${isSidebarOpen ? 'left-[calc(var(--sidebar-width)-16px)]' : 'left-4'}`}
              style={sidebarHandleStyle}
              title={isSidebarOpen ? "收起收藏夹" : "展开收藏夹"}
            >
              <svg className={`w-4 h-4 transition-transform ${isSidebarOpen ? '' : 'rotate-180'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>

            {/* 收藏夹气泡栏 */}
            <div
              className={`sidebar-shell ${isSidebarOpen ? "open" : "closed"}`}
              style={{ "--sidebar-width": `${sidebarWidth}px` } as React.CSSProperties}
            >
              <aside
                className="panel panel-sources"
                style={{
                  width: sidebarWidth,
                  opacity: isSidebarOpen ? 1 : 0,
                  transform: isSidebarOpen ? "translateX(0) scale(1)" : "translateX(-14px) scale(0.985)",
                  pointerEvents: isSidebarOpen ? "auto" : "none",
                  transition: "transform 340ms cubic-bezier(0.22,1,0.36,1), opacity 240ms ease",
                }}
              >
                <SourcesPanel
                  sessionId={session}
                  onBuildDone={() => setStatsKey((v) => v + 1)}
                  onSelectionChange={setSelectedFolderIds}
                />
              </aside>
            </div>

            {/* 拖拽分隔条 */}
            <div
              className={`resizer transition-[width,opacity] duration-300 ${isSidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"}`}
              onMouseDown={handleMouseDown}
              style={{ cursor: "col-resize", width: isSidebarOpen ? 8 : 0 }}
            />

            <section className={`panel-chat-embedded ${isSidebarOpen ? "" : "full-width"}`} style={{ flex: 1 }}>
              <ChatPanel
                statsKey={statsKey}
                sessionId={session ?? undefined}
                folderIds={selectedFolderIds}
                sidebarOpen={isSidebarOpen}
              />
            </section>
          </section>
        )}
      </main>

      {/* 右上角用户菜单 (替换原有的 N 字 UI 区域) */}
      <div className="fixed top-4 right-4 z-50 flex items-center gap-3">
        {user ? (
          <div className="relative group">
            <button className="w-10 h-10 rounded-full bg-black dark:bg-gray-800 text-white flex items-center justify-center font-bold shadow-lg ring-1 ring-black/10 dark:ring-white/10 hover:scale-[1.03] hover:ring-2 hover:ring-amber-400/70 transition-all duration-200">
              {userAvatar ? (
                <Image
                  src={userAvatar}
                  alt={`${user} 的头像`}
                  width={40}
                  height={40}
                  unoptimized
                  className="w-full h-full rounded-full object-cover"
                  referrerPolicy="no-referrer"
                  onError={() => setUserAvatar(null)}
                />
              ) : (
                user.charAt(0).toUpperCase()
              )}
            </button>
            <div className="pointer-events-none absolute top-full right-0 mt-2.5 w-36 rounded-2xl border border-(--border) bg-(--paper-2) shadow-[0_14px_30px_rgba(28,23,18,0.2)] backdrop-blur-md opacity-0 translate-y-1.5 scale-[0.98] origin-top-right transition-all duration-200 group-hover:pointer-events-auto group-hover:opacity-100 group-hover:translate-y-0 group-hover:scale-100 dark:bg-(--paper) dark:border-(--border)">
              <div className="px-3 pt-3 pb-6 border-b border-(--border) text-center">
                <div className="text-[10px] tracking-[0.08em] text-(--muted) mb-1">当前账号</div>
                <div className="text-xs font-semibold truncate text-(--ink-soft)">{user}</div>
              </div>
              <button 
                onClick={onLogout}
                className="w-full px-3 py-2 text-[11px] font-medium text-[#3f0909] hover:text-[#2b0505] hover:bg-[rgba(255,255,255,0.52)] dark:text-[#9f4d4d] dark:hover:text-[#b76868] dark:bg-[rgba(68,16,16,0.2)] dark:hover:bg-[rgba(86,20,20,0.28)] dark:border-t dark:border-[rgba(140,78,78,0.22)] rounded-b-2xl transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                退出登录
              </button>
            </div>
          </div>
        ) : (
          <button 
            onClick={() => setShowLogin(true)}
            className="w-10 h-10 rounded-full bg-black dark:bg-gray-800 text-white flex items-center justify-center shadow-lg hover:bg-gray-800 dark:hover:bg-gray-700 transition-colors"
            title="登录"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </button>
        )}

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
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          )}
        </button>
      </div>

      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} onSuccess={onLogin} />
      <DemoFlowModal isOpen={showDemo} onClose={() => setShowDemo(false)} />
    </div>
  );
}
