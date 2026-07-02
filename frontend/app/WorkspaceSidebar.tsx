import type { CSSProperties } from "react";

import ChatHistorySidebarPanel from "@/components/ChatHistorySidebarPanel";
import KnowledgeBasePanel from "@/components/KnowledgeBasePanel";
import NotesSidebarPanel from "@/components/NotesSidebarPanel";
import SourcesPanel from "@/components/SourcesPanel";
import type { SidebarMode } from "@/app/useWorkspaceState";
import type { KnowledgeBase } from "@/lib/api";

interface WorkspaceSidebarProps {
  activeBindingId: number | null;
  activeKbId: number | null;
  activeKnowledgeBase: KnowledgeBase | null;
  historyRefreshKey: number;
  isSidebarOpen: boolean;
  knowledgeBuilding: boolean;
  kbRefreshKey: number;
  sidebarMode: SidebarMode;
  sidebarPanelStyle: CSSProperties;
  sidebarWidth: number;
  onActiveKnowledgeBase: (knowledgeBase: KnowledgeBase | null) => void;
  onBuildingChange: (building: boolean) => void;
  onBuildDone: () => void;
  onCollapse: () => void;
  onImportClick: () => void;
  onKnowledgeBaseSelect: (knowledgeBase: KnowledgeBase | null) => void;
  onNewConversation: () => void;
  onOpenConversation: (conversationId: number) => void;
}

export default function WorkspaceSidebar({
  activeBindingId,
  activeKbId,
  activeKnowledgeBase,
  historyRefreshKey,
  isSidebarOpen,
  knowledgeBuilding,
  kbRefreshKey,
  sidebarMode,
  sidebarPanelStyle,
  sidebarWidth,
  onActiveKnowledgeBase,
  onBuildingChange,
  onBuildDone,
  onCollapse,
  onImportClick,
  onKnowledgeBaseSelect,
  onNewConversation,
  onOpenConversation,
}: WorkspaceSidebarProps) {
  return (
    <div
      className={`sidebar-shell ${isSidebarOpen ? "open" : "closed"}`}
      style={
        {
          "--sidebar-width": `${sidebarWidth}px`,
        } as CSSProperties
      }
    >
      <aside className="panel panel-sources" style={sidebarPanelStyle}>
        {sidebarMode === "sources" ? (
          <SourcesSidebarContent
            activeBindingId={activeBindingId}
            activeKbId={activeKbId}
            activeKnowledgeBase={activeKnowledgeBase}
            knowledgeBuilding={knowledgeBuilding}
            kbRefreshKey={kbRefreshKey}
            onActiveKnowledgeBase={onActiveKnowledgeBase}
            onBuildingChange={onBuildingChange}
            onBuildDone={onBuildDone}
            onImportClick={onImportClick}
            onKnowledgeBaseSelect={onKnowledgeBaseSelect}
          />
        ) : sidebarMode === "history" ? (
          <ChatHistorySidebarPanel
            knowledgeBaseId={activeKbId}
            refreshKey={historyRefreshKey}
            onOpenConversation={onOpenConversation}
            onNewConversation={onNewConversation}
            onCollapse={onCollapse}
          />
        ) : (
          <NotesSidebarPanel />
        )}
      </aside>
    </div>
  );
}

function SourcesSidebarContent({
  activeBindingId,
  activeKbId,
  activeKnowledgeBase,
  knowledgeBuilding,
  kbRefreshKey,
  onActiveKnowledgeBase,
  onBuildingChange,
  onBuildDone,
  onImportClick,
  onKnowledgeBaseSelect,
}: {
  activeBindingId: number | null;
  activeKbId: number | null;
  activeKnowledgeBase: KnowledgeBase | null;
  knowledgeBuilding: boolean;
  kbRefreshKey: number;
  onActiveKnowledgeBase: (knowledgeBase: KnowledgeBase | null) => void;
  onBuildingChange: (building: boolean) => void;
  onBuildDone: () => void;
  onImportClick: () => void;
  onKnowledgeBaseSelect: (knowledgeBase: KnowledgeBase | null) => void;
}) {
  return (
    <>
      <KnowledgeBasePanel
        activeId={activeKbId}
        onSelect={onKnowledgeBaseSelect}
        onActiveKnowledgeBase={onActiveKnowledgeBase}
        refreshKey={kbRefreshKey}
        disabled={knowledgeBuilding}
      />

      {!activeBindingId && <ImportSidebarEntry onImportClick={onImportClick} />}
      {activeBindingId ? (
        <SourcesPanel
          sourceBindingId={activeBindingId}
          knowledgeBaseId={activeKbId ?? 0}
          knowledgeBaseName={activeKnowledgeBase?.name}
          onImportClick={onImportClick}
          onBuildDone={onBuildDone}
          onBuildingChange={onBuildingChange}
        />
      ) : (
        <SourcesInitialEmpty onImportClick={onImportClick} />
      )}
    </>
  );
}

function ImportSidebarEntry({ onImportClick }: { onImportClick: () => void }) {
  return (
    <div className="import-sidebar-entry">
      <button onClick={onImportClick} className="import-sidebar-btn">
        + 导入
      </button>
      <p>选择 B 站收藏夹、视频 URL 或更多平台导入资料</p>
    </div>
  );
}

function SourcesInitialEmpty({ onImportClick }: { onImportClick: () => void }) {
  return (
    <div className="sources-initial-empty">
      <div className="sources-empty-card">
        <div className="sources-empty-kicker">收藏夹资料</div>
        <div className="sources-empty-title">暂无收藏夹资料</div>
        <p>导入 B 站收藏夹、视频 URL 或更多平台资料后，会显示在这里。</p>
        <button
          type="button"
          className="sources-empty-action"
          onClick={onImportClick}
        >
          选择资料来源
        </button>
      </div>
    </div>
  );
}
