"use client";

import { useState, useEffect } from "react";
import {
  displayKnowledgeBaseName,
  isMissingDisplayText,
} from "@/lib/displayNames";
import OrganizePreviewModal from "@/components/OrganizePreviewModal";
import SourcesFolderList from "@/components/sources/SourcesFolderList";
import VideoPlayerPortal, {
  type PlayingVideo,
} from "@/components/sources/VideoPlayerPortal";
import { useSourcesKnowledgeBuild } from "@/components/sources/useSourcesKnowledgeBuild";
import { useSourcesPanelActions } from "@/components/sources/useSourcesPanelActions";
import { useSourcesPanelData } from "@/components/sources/useSourcesPanelData";
import { getSourcesBuildButtonText } from "@/components/sources/sourcesPanelLogic";

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
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [selectedVideos, setSelectedVideos] = useState<Set<string>>(new Set());
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
      setSelected(new Set());
      setSelectedVideos(new Set());
      resetBuildProgress();
      setMessage(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [knowledgeBaseId, resetBuildProgress, setMessage, sourceBindingId]);

  // 刷新
  const refresh = async () => {
    await refreshSourcesData();
  };

  // 选择收藏夹
  const toggleSelect = (id: number) => {
    const s = new Set(selected);
    if (s.has(id)) {
      s.delete(id);
    } else {
      s.add(id);
      const folder = folders.find((f) => f.media_id === id);
      if (folder?.videos?.length) {
        setSelectedVideos((prev) => {
          const next = new Set(prev);
          folder.videos?.forEach((video) => next.delete(video.bvid));
          return next;
        });
      }
    }
    setSelected(s);
  };

  const toggleVideoSelect = (folderId: number, bvid: string) => {
    if (selected.has(folderId)) {
      const nextFolders = new Set(selected);
      nextFolders.delete(folderId);
      setSelected(nextFolders);
    }
    setSelectedVideos((prev) => {
      const next = new Set(prev);
      if (next.has(bvid)) {
        next.delete(bvid);
      } else {
        next.add(bvid);
      }
      return next;
    });
  };

  const isEmptyState = !loading && folders.length === 0;

  return (
    <div
      className={
        isEmptyState ? "panel-inner sources-panel-empty" : "panel-inner"
      }
    >
      <div className="sources-panel-head">
        <div className="sources-panel-head-top">
          <div className="sources-panel-title">收藏夹资料</div>
          <button
            type="button"
            className="sources-panel-action import-action"
            onClick={onImportClick}
          >
            + 导入
          </button>
        </div>
        <div className="sources-panel-head-bottom">
          <div className="sources-panel-subtitle">
            勾选后入库到{targetKnowledgeBase}
          </div>
          <div className="sources-panel-actions">
            <button
              onClick={() => {
                const def = folders.find(
                  (f) => f.is_default || f.title === "默认收藏夹",
                );
                if (def) {
                  void openOrganizePreview(def.media_id);
                } else {
                  setOrganizeMessage("未找到默认收藏夹");
                }
              }}
              className="sources-panel-action"
              title="快速整理默认收藏夹"
              disabled={loading || organizeLoading}
            >
              {organizeLoading ? "整理中" : "整理"}
            </button>
            <button
              onClick={refresh}
              className="sources-panel-action"
              disabled={loading}
              title={loading ? "加载中..." : "刷新"}
              aria-label={loading ? "加载中..." : "刷新"}
            >
              {loading ? "刷新中" : "刷新"}
            </button>
          </div>
        </div>
      </div>

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
            <div className="sources-empty-state">
              <div className="sources-empty-card">
                <div className="sources-empty-kicker">收藏夹资料</div>
                <div className="sources-empty-title">暂无收藏夹资料</div>
                <p>当前账号暂未读取到收藏夹，或收藏夹资料还没有完成同步。</p>
                {onImportClick && (
                  <button
                    type="button"
                    className="sources-empty-action"
                    onClick={onImportClick}
                  >
                    导入更多资料
                  </button>
                )}
              </div>
            </div>
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
              onToggleFolderSelect={toggleSelect}
              onToggleVideoSelect={toggleVideoSelect}
              onVideoNameChange={setEditingVideoName}
            />
          )}
        </div>
      </div>

      <div className="panel-footer">
        {/* 进度条 */}
        {progress && building && (
          <div className="mb-4">
            <div className="flex justify-between text-xs mb-2">
              <span className="text-(--muted) truncate">
                {progress.current_step}
              </span>
              <span className="text-(--accent)">{progress.progress}%</span>
            </div>
            <div className="progress">
              <div
                className="progress-bar"
                style={{ width: `${progress.progress}%` }}
              />
            </div>
          </div>
        )}

        {/* 消息 */}
        {message && (
          <div className="text-xs text-(--muted) mb-3">{message}</div>
        )}
        {organizeMessage && (
          <div className="text-xs text-(--muted) mb-3">{organizeMessage}</div>
        )}

        {/* 主按钮 */}
        <button
          onClick={startBuild}
          disabled={
            (selected.size === 0 && selectedVideos.size === 0) ||
            building ||
            !knowledgeBaseId
          }
          className={`sources-ingest-button ${
            (selected.size > 0 || selectedVideos.size > 0) && knowledgeBaseId
              ? "active"
              : "idle"
          }`}
        >
          {knowledgeBaseId
            ? getSourcesBuildButtonText({
                building,
                progressStep: progress?.current_step,
                selectedCount: selected.size,
                selectedVideoCount: selectedVideos.size,
                selectedFolderIds: Array.from(selected),
                targetKnowledgeBase,
                folders,
                statusMap,
              })
            : "请先在侧栏创建知识库"}
        </button>

        {knowledgeBaseId ? (
          <p className="sources-ingest-hint">
            入库到 {targetKnowledgeBase} 后，可在右侧选择收藏夹或视频提问
          </p>
        ) : (
          <p className="sources-ingest-hint">
            创建知识库后即可将收藏夹内容入库
          </p>
        )}
      </div>

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
