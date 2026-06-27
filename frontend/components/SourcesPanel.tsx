"use client";

import { useState, useEffect, useCallback } from "react";
import {
  FavoriteFolder,
  Video,
  sourceBindingApi,
  knowledgeBaseApi,
  BuildStatus,
  FolderStatus,
  OrganizePreviewResponse,
  KnowledgeBaseBuildRequest,
} from "@/lib/api";
import {
  displayFolderTitle,
  displayKnowledgeBaseName,
  displayVideoTitle,
  isMissingDisplayText,
} from "@/lib/displayNames";
import OrganizePreviewModal from "@/components/OrganizePreviewModal";
import VideoPlayerPortal, {
  type PlayingVideo,
} from "@/components/sources/VideoPlayerPortal";
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
  const [folders, setFolders] = useState<
    (FavoriteFolder & {
      videos?: Video[];
      expanded?: boolean;
      loading?: boolean;
      count_source?: "bili" | "filtered" | "db";
    })[]
  >([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [selectedVideos, setSelectedVideos] = useState<Set<string>>(new Set());
  const [customVideoNames, setCustomVideoNames] = useState<
    Record<string, string>
  >({});
  const [editingVideoId, setEditingVideoId] = useState<string | null>(null);
  const [editingVideoName, setEditingVideoName] = useState("");
  const [savingVideoId, setSavingVideoId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [progress, setProgress] = useState<BuildStatus | null>(null);
  const [statusMap, setStatusMap] = useState<Record<number, FolderStatus>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [organizeOpen, setOrganizeOpen] = useState(false);
  const [organizeLoading, setOrganizeLoading] = useState(false);
  const [organizePreview, setOrganizePreview] =
    useState<OrganizePreviewResponse | null>(null);
  const [organizeMessage, setOrganizeMessage] = useState<string | null>(null);
  const [playingVideo, setPlayingVideo] = useState<PlayingVideo | null>(null);
  const targetKnowledgeBase = !isMissingDisplayText(knowledgeBaseName)
    ? `「${displayKnowledgeBaseName(knowledgeBaseName)}」`
    : "当前知识库";

  // 加载收藏夹列表（从B站获取）
  const loadFolders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sourceBindingApi.getFavorites(sourceBindingId);
      setFolders(data.map((f) => ({ ...f, count_source: "bili" })));
      setMessage(null);
    } catch (err) {
      setFolders([]);
      setMessage(
        err instanceof Error ? err.message : "加载收藏夹失败，请稍后重试",
      );
    }
    setLoading(false);
  }, [sourceBindingId]);

  // 加载入库状态（从知识库 scoped API）
  const loadStatuses = useCallback(async () => {
    if (!knowledgeBaseId) return;
    try {
      const stats = await knowledgeBaseApi.stats(knowledgeBaseId);
      const map: Record<number, FolderStatus> = {};
      if (stats.folders) {
        stats.folders.forEach(
          (f: {
            media_id: number;
            indexed_count: number;
            media_count: number;
            last_sync_at: string | null;
          }) => {
            map[f.media_id] = {
              media_id: f.media_id,
              indexed_count: f.indexed_count,
              media_count: f.media_count,
              last_sync_at: f.last_sync_at,
            };
          },
        );
      }
      setStatusMap(map);
    } catch {
      // 状态接口失败不影响主列表展示
    }
  }, [knowledgeBaseId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadFolders().then(loadStatuses);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadFolders, loadStatuses]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSelected(new Set());
      setSelectedVideos(new Set());
      setProgress(null);
      setMessage(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [sourceBindingId, knowledgeBaseId]);

  useEffect(() => {
    onBuildingChange?.(building);
    return () => onBuildingChange?.(false);
  }, [building, onBuildingChange]);

  const getVideoTitle = (video: Video) =>
    displayVideoTitle(
      customVideoNames[video.bvid] ||
        video.display_title ||
        video.custom_title ||
        video.title,
    );

  const getOriginalVideoTitle = (video: Video) =>
    displayVideoTitle(video.original_title || video.title);

  const startRenameVideo = (video: Video) => {
    setEditingVideoId(video.bvid);
    setEditingVideoName(getVideoTitle(video));
  };

  const applyVideoTitle = (
    videos: Video[] | undefined,
    bvid: string,
    customTitle: string | null,
  ) =>
    videos?.map((video) =>
      video.bvid === bvid
        ? {
            ...video,
            custom_title: customTitle,
            display_title: customTitle || getOriginalVideoTitle(video),
            title: customTitle || getOriginalVideoTitle(video),
          }
        : video,
    );

  const saveVideoTitle = async (video: Video, title: string) => {
    const originalTitle = getOriginalVideoTitle(video);
    const trimmed = title.trim();
    const customTitle = !trimmed || trimmed === originalTitle ? null : trimmed;
    setSavingVideoId(video.bvid);
    try {
      const res = await sourceBindingApi.updateVideoTitle(sourceBindingId, {
        bvid: video.bvid,
        title: customTitle,
        knowledge_base_id: knowledgeBaseId,
      });
      const nextCustomTitle = res.custom_title ?? null;
      setCustomVideoNames((prev) => {
        const next = { ...prev };
        if (nextCustomTitle) {
          next[video.bvid] = nextCustomTitle;
        } else {
          delete next[video.bvid];
        }
        return next;
      });
      setFolders((prev) =>
        prev.map((folder) => ({
          ...folder,
          videos: applyVideoTitle(folder.videos, video.bvid, nextCustomTitle),
        })),
      );
      setEditingVideoId(null);
      setEditingVideoName("");
      setMessage(nextCustomTitle ? "已保存自定义视频名" : "已恢复原始视频名");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "保存视频名称失败");
    } finally {
      setSavingVideoId(null);
    }
  };

  // 刷新
  const refresh = async () => {
    setMessage(null);
    await loadFolders();
    await loadStatuses();
  };

  const openOrganizePreview = async (folderId: number) => {
    setOrganizeMessage(null);
    setOrganizePreview(null);
    setOrganizeOpen(true);
    setOrganizeLoading(true);
    try {
      const res = await sourceBindingApi.organizePreview(
        sourceBindingId,
        folderId,
      );
      setOrganizePreview(res);
    } catch {
      setOrganizeMessage("预览失败，请稍后重试");
    } finally {
      setOrganizeLoading(false);
    }
  };

  // 展开收藏夹查看视频
  const toggleExpand = async (id: number) => {
    setFolders((prev) =>
      prev.map((f) => {
        if (f.media_id !== id) return f;
        if (f.expanded) return { ...f, expanded: false };
        if (f.videos) return { ...f, expanded: true };
        return { ...f, expanded: true, loading: true };
      }),
    );

    const folder = folders.find((f) => f.media_id === id);
    if (!folder?.videos) {
      try {
        const res = await sourceBindingApi.getAllFavoriteVideos(
          sourceBindingId,
          id,
          knowledgeBaseId,
        );
        setFolders((prev) =>
          prev.map((f) =>
            f.media_id === id
              ? {
                  ...f,
                  videos: res.videos,
                  loading: false,
                  media_count: res.total,
                  count_source: "filtered",
                }
              : f,
          ),
        );
      } catch {
        setFolders((prev) =>
          prev.map((f) => (f.media_id === id ? { ...f, loading: false } : f)),
        );
      }
    }
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

  const getSelectedVideoFolderIds = () => {
    const folderIds = new Set<number>();
    folders.forEach((folder) => {
      folder.videos?.forEach((video) => {
        if (selectedVideos.has(video.bvid) && !selected.has(folder.media_id)) {
          folderIds.add(folder.media_id);
        }
      });
    });
    return Array.from(folderIds);
  };

  // 构建/更新知识库（统一操作）
  const buildKnowledge = async () => {
    if (selected.size === 0 && selectedVideos.size === 0) return;
    setBuilding(true);
    setMessage(null);
    setProgress(null);

    try {
      const selectedVideoBvids = Array.from(selectedVideos);
      const videoFolderIds = getSelectedVideoFolderIds();
      const res = await knowledgeBaseApi.build(knowledgeBaseId, {
        source_binding_id: sourceBindingId,
        folder_ids: Array.from(selected),
        ...(selectedVideoBvids.length > 0
          ? { video_folder_ids: videoFolderIds, bvids: selectedVideoBvids }
          : {}),
        ...(excludeBvids.length > 0 ? { exclude_bvids: excludeBvids } : {}),
      } as KnowledgeBaseBuildRequest);

      const poll = async () => {
        const s = await knowledgeBaseApi.getBuildStatus(
          knowledgeBaseId,
          res.task_id,
        );
        setProgress(s);

        if (s.status === "running" || s.status === "pending") {
          setTimeout(poll, 1000);
        } else {
          setBuilding(false);
          if (s.status === "completed") {
            setMessage(s.message || "构建完成");
            await loadStatuses();
            onBuildDone?.();
          } else if (s.status === "failed") {
            setMessage(`构建失败: ${s.message}`);
          } else if (s.status === "interrupted") {
            setMessage(`构建已中断: ${s.message || "请重新发起"}`);
          } else {
            setMessage(s.message || `构建已停止: ${s.status}`);
          }
        }
      };
      poll();
    } catch {
      setBuilding(false);
      setMessage("构建失败，请重试");
    }
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
                  openOrganizePreview(def.media_id);
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
          onClick={buildKnowledge}
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
