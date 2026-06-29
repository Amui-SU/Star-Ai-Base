"use client";

import { useState, useEffect } from "react";
import {
  displayFolderTitle,
  displayKnowledgeBaseName,
  isMissingDisplayText,
} from "@/lib/displayNames";
import OrganizePreviewModal from "@/components/OrganizePreviewModal";
import VideoPlayerPortal, {
  type PlayingVideo,
} from "@/components/sources/VideoPlayerPortal";
import { useSourcesKnowledgeBuild } from "@/components/sources/useSourcesKnowledgeBuild";
import { useSourcesPanelActions } from "@/components/sources/useSourcesPanelActions";
import { useSourcesPanelData } from "@/components/sources/useSourcesPanelData";
import {
  formatFolderSyncTime,
  getSourcesBuildButtonText,
  getSourcesFolderStatus,
} from "@/components/sources/sourcesPanelLogic";

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
            <div className="sources-folder-list">
              {folders.map((f) => {
                const status = getSourcesFolderStatus({
                  folders,
                  statusMap,
                  mediaId: f.media_id,
                  totalInBilibili: f.media_count,
                });
                const lastSync = formatFolderSyncTime(
                  statusMap[f.media_id]?.last_sync_at ?? undefined,
                );
                const folderTitle = displayFolderTitle(f.title);

                return (
                  <div
                    key={f.media_id}
                    className={`folder-card ${selected.has(f.media_id) ? "selected" : ""}`}
                  >
                    <div
                      className="folder-head"
                      onClick={() => toggleExpand(f.media_id)}
                    >
                      <input
                        type="checkbox"
                        checked={selected.has(f.media_id)}
                        onChange={() => toggleSelect(f.media_id)}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`选择收藏夹 ${folderTitle}`}
                        className="folder-checkbox"
                      />
                      <div className="folder-meta">
                        <div className="folder-title" title={folderTitle}>
                          {folderTitle}
                        </div>
                        <div className="folder-count">
                          {status.indexedCount}/
                          {status.totalCount ?? f.media_count} 个视频
                          {lastSync && ` · ${lastSync}`}
                        </div>
                      </div>
                      <span className={`status-pill ${status.className}`}>
                        {status.label}
                      </span>
                      <div className="folder-toggle">
                        <svg
                          className={`w-4 h-4 transition-transform ${f.expanded ? "rotate-90" : ""}`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 5l7 7-7 7"
                          />
                        </svg>
                      </div>
                    </div>

                    <div
                      className={`folder-list-wrapper ${f.expanded ? "expanded" : ""}`}
                    >
                      <div className="folder-list">
                        {f.loading ? (
                          <div className="text-xs text-(--muted)">
                            加载中...
                          </div>
                        ) : f.videos?.length === 0 ? (
                          <div className="text-xs text-(--muted)">暂无视频</div>
                        ) : (
                          f.videos?.map((v) => {
                            const displayTitle = getVideoTitle(v);
                            const originalTitle = getOriginalVideoTitle(v);
                            const isEditing = editingVideoId === v.bvid;
                            const isSaving = savingVideoId === v.bvid;

                            return (
                              <div key={v.bvid} className="video-card">
                                <input
                                  type="checkbox"
                                  className="video-checkbox"
                                  checked={
                                    selected.has(f.media_id) ||
                                    selectedVideos.has(v.bvid)
                                  }
                                  onChange={() =>
                                    toggleVideoSelect(f.media_id, v.bvid)
                                  }
                                  onClick={(event) => event.stopPropagation()}
                                  aria-label={`选择视频 ${displayTitle}`}
                                />
                                <button
                                  type="button"
                                  className="video-play-btn"
                                  onClick={() =>
                                    setPlayingVideo({
                                      bvid: v.bvid,
                                      title: displayTitle,
                                    })
                                  }
                                  title="在线播放"
                                  aria-label={`播放 ${displayTitle}`}
                                >
                                  ▶
                                </button>
                                <div className="video-card-body">
                                  {isEditing ? (
                                    <input
                                      className="video-title-input"
                                      value={editingVideoName}
                                      onChange={(event) =>
                                        setEditingVideoName(event.target.value)
                                      }
                                      autoFocus
                                      onKeyDown={(event) => {
                                        if (event.key === "Enter") {
                                          void saveVideoTitle(
                                            v,
                                            editingVideoName,
                                          );
                                        }
                                        if (event.key === "Escape") {
                                          setEditingVideoId(null);
                                          setEditingVideoName("");
                                        }
                                      }}
                                    />
                                  ) : (
                                    <a
                                      href={`https://www.bilibili.com/video/${v.bvid}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="video-card-title truncate"
                                      aria-label={displayTitle}
                                    >
                                      {displayTitle}
                                    </a>
                                  )}
                                  <div className="video-card-meta">
                                    <span title={originalTitle}>
                                      {originalTitle}
                                    </span>
                                    {v.custom_title &&
                                      v.custom_title !== originalTitle && (
                                        <span className="video-card-badge">
                                          自定义
                                        </span>
                                      )}
                                  </div>
                                </div>
                                <div className="video-card-actions">
                                  {isEditing ? (
                                    <>
                                      <button
                                        type="button"
                                        className="video-card-action primary"
                                        onClick={() =>
                                          void saveVideoTitle(
                                            v,
                                            editingVideoName,
                                          )
                                        }
                                        disabled={isSaving}
                                      >
                                        {isSaving ? "保存中" : "保存"}
                                      </button>
                                      <button
                                        type="button"
                                        className="video-card-action"
                                        onClick={() => {
                                          setEditingVideoId(null);
                                          setEditingVideoName("");
                                        }}
                                        disabled={isSaving}
                                      >
                                        取消
                                      </button>
                                    </>
                                  ) : (
                                    <>
                                      <button
                                        type="button"
                                        className="video-card-action"
                                        onClick={() => startRenameVideo(v)}
                                      >
                                        重命名
                                      </button>
                                      {(v.custom_title ||
                                        getVideoTitle(v) !== originalTitle) && (
                                        <button
                                          type="button"
                                          className="video-card-action"
                                          onClick={() =>
                                            void saveVideoTitle(
                                              v,
                                              originalTitle,
                                            )
                                          }
                                        >
                                          恢复
                                        </button>
                                      )}
                                    </>
                                  )}
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
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
