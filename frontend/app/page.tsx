"use client";

import AuthPage from "@/components/AuthPage";
import ImportModal from "@/components/ImportModal";
import ChatPanel from "@/components/ChatPanel";
import AdminUsersPanel from "@/components/AdminUsersPanel";
import ApiAccountsPanel from "@/components/ApiAccountsPanel";
import VideoNoteWorkspace from "@/components/video-notes/VideoNoteWorkspace";
import { useTheme } from "@/hooks/useTheme";
import { useHomePageShell } from "@/app/useHomePageShell";
import { useWorkspaceState } from "@/app/useWorkspaceState";
import WorkspaceCornerTools from "@/app/WorkspaceCornerTools";
import WorkspaceResizer from "@/app/WorkspaceResizer";
import WorkspaceSidebar from "@/app/WorkspaceSidebar";
import WorkspaceSidebarToggle from "@/app/WorkspaceSidebarToggle";
import WorkspaceTopbar from "@/app/WorkspaceTopbar";

export default function Home() {
  const { isDarkMode, ready: themeReady, toggleTheme } = useTheme();
  const shell = useHomePageShell();
  const {
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
    activeVideoNote,
    openSidebarMode,
    collapseSidebar,
    requestOpenConversation,
    requestNewConversation,
    refreshHistory,
    openVideoNoteWorkspace,
    closeVideoNoteWorkspace,
  } = useWorkspaceState();

  // 加载中
  if (shell.authChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-(--bg)">
        <div className="w-8 h-8 border-2 border-(--accent) border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // 未登录 → 显示 AuthPage
  if (!shell.systemUser) {
    return <AuthPage onAuthSuccess={shell.handleAuthSuccess} />;
  }

  // 已登录 → 工作台
  return (
    <div
      className={`app-shell ${isSidebarOpen ? "sidebar-open" : "sidebar-closed"}`}
    >
      <main className="app-main">
        <section className="workspace-card relative" ref={containerRef}>
          <WorkspaceTopbar
            isDarkMode={isDarkMode}
            themeReady={themeReady}
            user={shell.systemUser}
            onLogout={shell.handleLogout}
            onOpenAdmin={shell.openAdminUsers}
            onOpenApiAccounts={shell.openApiAccounts}
            onThemeToggle={toggleTheme}
            onUserChange={shell.setSystemUser}
          />

          <div
            className={`workspace ${activeVideoNote ? "video-note-open" : ""}`}
          >
            {!isSidebarOpen && (
              <WorkspaceCornerTools
                onOpenSidebarMode={openSidebarMode}
                onOpenNotes={() => {
                  if (shell.activeKbId) {
                    openVideoNoteWorkspace(null);
                  } else {
                    openSidebarMode("sources");
                  }
                }}
              />
            )}

            {isSidebarOpen && sidebarMode !== "history" && (
              <WorkspaceSidebarToggle
                style={sidebarHandleStyle}
                onCollapse={collapseSidebar}
              />
            )}

            <WorkspaceSidebar
              activeBindingId={shell.activeBindingId}
              activeKbId={shell.activeKbId}
              activeKnowledgeBase={shell.activeKnowledgeBase}
              historyRefreshKey={historyRefreshKey}
              isSidebarOpen={isSidebarOpen}
              knowledgeBuilding={shell.knowledgeBuilding}
              kbRefreshKey={shell.kbRefreshKey}
              sidebarMode={sidebarMode}
              sidebarPanelStyle={sidebarPanelStyle}
              sidebarWidth={sidebarWidth}
              onActiveKnowledgeBase={shell.setActiveKnowledgeBase}
              onBuildingChange={shell.setKnowledgeBuilding}
              onBuildDone={shell.markStatsChanged}
              onCollapse={collapseSidebar}
              onImportClick={shell.openImport}
              onKnowledgeBaseSelect={shell.handleKnowledgeBaseSelect}
              onNewConversation={requestNewConversation}
              onOpenVideoNotes={() => openVideoNoteWorkspace(null)}
              onOpenVideoNote={openVideoNoteWorkspace}
              onOpenConversation={requestOpenConversation}
            />

            <WorkspaceResizer
              isSidebarOpen={isSidebarOpen}
              onMouseDown={handleMouseDown}
            />

            {activeVideoNote && shell.activeKbId && (
              <VideoNoteWorkspace
                key={activeVideoNote.key}
                knowledgeBaseId={shell.activeKbId}
                knowledgeBaseName={shell.activeKnowledgeBase?.name}
                initialBvid={activeVideoNote.bvid}
                onClose={closeVideoNoteWorkspace}
              />
            )}

            <section
              className={`panel-chat-embedded ${isSidebarOpen ? "" : "full-width"}`}
              style={{ flex: 1 }}
            >
              <ChatPanel
                statsKey={shell.statsKey}
                sidebarOpen={isSidebarOpen}
                sidebarWidth={sidebarWidth}
                knowledgeBaseId={shell.activeKbId}
                knowledgeBaseName={shell.activeKnowledgeBase?.name}
                isAdmin={Boolean(shell.systemUser?.is_admin)}
                apiAccountsKey={shell.apiAccountsKey}
                onOpenApiAccounts={shell.openApiAccounts}
                conversationOpenRequest={conversationOpenRequest}
                newConversationRequestKey={newConversationRequestKey}
                onConversationSaved={refreshHistory}
                onOpenVideoNote={openVideoNoteWorkspace}
              />
            </section>
          </div>
        </section>
      </main>

      <ImportModal
        open={shell.showImport}
        knowledgeBaseId={shell.activeKbId}
        hasBilibiliBinding={!!shell.activeBindingId}
        onClose={shell.closeImport}
        onBound={shell.handleBiliBound}
        onImported={shell.markStatsChanged}
      />
      <AdminUsersPanel
        open={shell.showAdminUsers}
        currentUserId={shell.systemUser.id}
        onClose={shell.closeAdminUsers}
      />
      <ApiAccountsPanel
        open={shell.showApiAccounts}
        onClose={shell.closeApiAccounts}
        onChanged={shell.markApiAccountsChanged}
      />
    </div>
  );
}
