"use client";

import { useState, useEffect } from "react";
import {
  displayKnowledgeBaseName,
  isMissingDisplayText,
} from "@/lib/displayNames";
import OrganizePreviewModal from "@/components/OrganizePreviewModal";
import SourcesEmptyState from "@/components/sources/SourcesEmptyState";
import SourcesFolderList from "@/components/sources/SourcesFolderList";
import SourcesPanelFooter from "@/components/sources/SourcesPanelFooter";
import SourcesPanelHeader from "@/components/sources/SourcesPanelHeader";
import VideoPlayerPortal, {
  type PlayingVideo,
} from "@/components/sources/VideoPlayerPortal";
import { useSourcesSelection } from "@/components/sources/useSourcesSelection";
import { useSourcesKnowledgeBuild } from "@/components/sources/useSourcesKnowledgeBuild";
import { useSourcesPanelActions } from "@/components/sources/useSourcesPanelActions";
import { useSourcesPanelData } from "@/components/sources/useSourcesPanelData";

interface Props {
  sourceBindingId: number;
  knowledgeBaseId: number;
  knowledgeBaseName?: string;
  excludeBvids?: string[];
  onImportClick?: () => void;
  onBuildDone?: () => void;
  onBuildingChange?: (building: boolean) => void;
}

export default function SourcesPanel({
  sourceBindingId,
  knowledgeBaseId,
  knowledgeBaseName,
  excludeBvids = [],
  onImportClick,
  onBuildDone,
  onBuildingChange,
}: Props) {
  const [playingVideo, setPlayingVideo] = useState<PlayingVideo | null>(null);
  const targetKnowledgeBase = !isMissingDisplayText(knowledgeBaseName)
    ? `「${displayKnowledgeBaseName(knowledgeBaseName)}」`
    : "当前知识库";

  const {
    folders,
    loading,
    loadStatuses,
    message,
    refreshSourcesData,
    setFolders,
    setMessage,
    statusMap,
  } = useSourcesPanelData({
    sourceBindingId,
    knowledgeBaseId,
  });
  const {
    resetSelection,
    selected,
    selectedVideos,
    toggleFolderSelection,
    toggleVideoSelection,
  } = useSourcesSelection(folders);
  const { building, progress, resetBuildProgress, startBuild } =
    useSourcesKnowledgeBuild({
      excludeBvids,
      folders,
      knowledgeBaseId,
      onBuildDone,
      onBuildingChange,
      onLoadStatuses: loadStatuses,
      onMessage: setMessage,
      selected,
      selectedVideos,
      sourceBindingId,
    });
  const {
    editingVideoId,
    editingVideoName,
    getOriginalVideoTitle,
    getVideoTitle,
    organizeLoading,
    organizeMessage,
    organizeOpen,
    organizePreview,
    openOrganizePreview,
    saveVideoTitle,
    savingVideoId,
    setEditingVideoId,
    setEditingVideoName,
    setOrganizeMessage,
    setOrganizeOpen,
    startRenameVideo,
    toggleExpand,
  } = useSourcesPanelActions({
    folders,
    knowledgeBaseId,
    onMessage: setMessage,
    setFolders,
    sourceBindingId,
  });

  useEffect(() => {
    const timer = window.setTimeout(() => {
      resetSelection();
      resetBuildProgress();
      setMessage(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [
    knowledgeBaseId,
    resetBuildProgress,
    resetSelection,
    setMessage,
    sourceBindingId,
  ]);

  const refresh = async () => {
    await refreshSourcesData();
  };

  const isEmptyState = !loading && folders.length === 0;

  return (
    <div
      className={
        isEmptyState ? "panel-inner sources-panel-empty" : "panel-inner"
      }
    >
      <SourcesPanelHeader
        folders={folders}
        loading={loading}
        organizeLoading={organizeLoading}
        targetKnowledgeBase={targetKnowledgeBase}
        onImportClick={onImportClick}
        onOpenOrganizePreview={openOrganizePreview}
        onOrganizeMessage={setOrganizeMessage}
        onRefresh={refresh}
      />

      <div className="panel-body">
        <div
          className={
            isEmptyState
              ? "sources-scroll sources-scroll-empty"
              : "sources-scroll"
          }
        >
          {loading ? (
            <div className="text-center text-sm text-(--muted) py-6">
              加载中...
            </div>
          ) : folders.length === 0 ? (
            <SourcesEmptyState onImportClick={onImportClick} />
          ) : (
            <SourcesFolderList
              editingVideoId={editingVideoId}
              editingVideoName={editingVideoName}
              folders={folders}
              savingVideoId={savingVideoId}
              selected={selected}
              selectedVideos={selectedVideos}
              statusMap={statusMap}
              getOriginalVideoTitle={getOriginalVideoTitle}
              getVideoTitle={getVideoTitle}
              onCancelVideoEdit={() => {
                setEditingVideoId(null);
                setEditingVideoName("");
              }}
              onPlayVideo={setPlayingVideo}
              onRenameVideo={startRenameVideo}
              onSaveVideoTitle={(video, title) =>
                void saveVideoTitle(video, title)
              }
              onToggleFolder={toggleExpand}
              onToggleFolderSelect={toggleFolderSelection}
              onToggleVideoSelect={toggleVideoSelection}
              onVideoNameChange={setEditingVideoName}
            />
          )}
        </div>
      </div>

      <SourcesPanelFooter
        building={building}
        folders={folders}
        knowledgeBaseId={knowledgeBaseId}
        message={message}
        organizeMessage={organizeMessage}
        progress={progress}
        selected={selected}
        selectedVideos={selectedVideos}
        statusMap={statusMap}
        targetKnowledgeBase={targetKnowledgeBase}
        onStartBuild={startBuild}
      />

      <OrganizePreviewModal
        open={organizeOpen}
        bindingId={sourceBindingId}
        preview={organizePreview}
        loading={organizeLoading}
        errorMessage={organizeMessage}
        onClose={() => setOrganizeOpen(false)}
        onApplied={refresh}
      />

      <VideoPlayerPortal
        video={playingVideo}
        onClose={() => setPlayingVideo(null)}
      />
    </div>
  );
}
