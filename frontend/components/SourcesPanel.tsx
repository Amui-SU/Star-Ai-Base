"use client";

import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
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
import OrganizePreviewModal from "@/components/OrganizePreviewModal";

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
  const [playingVideo, setPlayingVideo] = useState<{
    bvid: string;
    title: string;
  } | null>(null);
  const targetKnowledgeBase = knowledgeBaseName
    ? `「${knowledgeBaseName}」`
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
    customVideoNames[video.bvid] ||
    video.display_title ||
    video.custom_title ||
    video.title;

  const getOriginalVideoTitle = (video: Video) =>
    video.original_title || video.title || video.bvid;

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
    }
    setSelected(s);
  };

  // 构建/更新知识库（统一操作）
  const buildKnowledge = async () => {
    if (selected.size === 0) return;
    setBuilding(true);
    setMessage(null);
    setProgress(null);

    try {
      const res = await knowledgeBaseApi.build(knowledgeBaseId, {
        source_binding_id: sourceBindingId,
        folder_ids: Array.from(selected),
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
          }
        }
      };
      poll();
    } catch {
      setBuilding(false);
      setMessage("构建失败，请重试");
    }
  };

  // 格式化时间
  const formatTime = (value?: string) => {
    if (!value) return null;
    try {
      let dateStr = value;
      if (!value.includes("T") && !value.includes("Z")) {
        dateStr = value.replace(" ", "T") + "Z";
      }
      const date = new Date(dateStr);
      if (Number.isNaN(date.getTime())) return null;

      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      const hour = String(date.getHours()).padStart(2, "0");
      const minute = String(date.getMinutes()).padStart(2, "0");
      return `${month}/${day} ${hour}:${minute}`;
    } catch {
      return null;
    }
  };

  // 获取收藏夹状态
  const getFolderStatus = (mediaId: number, totalInBilibili: number) => {
    const status = statusMap[mediaId];
    const indexedCount = status?.indexed_count ?? 0;
    const lastSync = status?.last_sync_at;
    const folder = folders.find((f) => f.media_id === mediaId);
    const countSource = folder?.count_source ?? "bili";
    let totalCount = totalInBilibili;
    if (countSource === "filtered") {
      totalCount = folder?.media_count ?? totalInBilibili;
    } else if (status?.media_count != null) {
      totalCount = status.media_count;
    }

    // 未入库：从未同步过
    if (!lastSync) {
      return { label: "未入库", className: "empty", indexedCount };
    }

    // 已入库：有同步时间
    if (indexedCount >= totalCount) {
      return { label: "已入库", className: "ok", indexedCount, totalCount };
    }

    // 有更新：B站收藏夹比本地多
    if (indexedCount < totalCount && indexedCount > 0) {
      return {
        label: "有更新",
        className: "partial",
        indexedCount,
        totalCount,
      };
    }

    // 已入库但视频数为0（可能视频都没有内容）
    return { label: "已入库", className: "ok", indexedCount, totalCount };
  };

  // 计算按钮文字
  const getButtonText = () => {
    if (building) return progress?.current_step || "处理中...";
    if (selected.size === 0) return "选择收藏夹";

    // 检查选中的是否有未入库的
    const hasUnindexed = Array.from(selected).some((id) => {
      const folder = folders.find((f) => f.media_id === id);
      if (!folder) return false;
      return !statusMap[id]?.last_sync_at;
    });

    if (hasUnindexed) {
      return `入库 ${selected.size} 个收藏夹到${targetKnowledgeBase}`;
    }
    return `更新 ${selected.size} 个收藏夹到${targetKnowledgeBase}`;
  };

  return (
    <div className="panel-inner">
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
        <div className="sources-scroll">
          {loading ? (
            <div className="text-center text-sm text-(--muted) py-6">
              加载中...
            </div>
          ) : folders.length === 0 ? (
            <div className="sources-empty-state">
              <div className="sources-empty-copy">暂无收藏夹</div>
            </div>
          ) : (
            <div className="sources-folder-list">
              {folders.map((f) => {
                const status = getFolderStatus(f.media_id, f.media_count);
                const lastSync = formatTime(
                  statusMap[f.media_id]?.last_sync_at ?? undefined,
                );

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
                        aria-label={`选择收藏夹 ${f.title}`}
                        className="folder-checkbox"
                      />
                      <div className="folder-meta">
                        <div className="folder-title" title={f.title}>
                          {f.title}
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
          disabled={selected.size === 0 || building || !knowledgeBaseId}
          className={`sources-ingest-button ${
            selected.size > 0 && knowledgeBaseId ? "active" : "idle"
          }`}
        >
          {knowledgeBaseId ? getButtonText() : "请先在侧栏创建知识库"}
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

      {playingVideo &&
        typeof document !== "undefined" &&
        createPortal(
          <div className="modal-backdrop" onClick={() => setPlayingVideo(null)}>
            <div
              className="modal-card video-player-modal"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="video-player-header">
                <div
                  className="video-player-title truncate"
                  title={playingVideo.title}
                >
                  {playingVideo.title}
                </div>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setPlayingVideo(null)}
                  title="关闭"
                >
                  关闭
                </button>
              </div>
              <iframe
                className="video-player-frame"
                src={`https://player.bilibili.com/player.html?bvid=${playingVideo.bvid}&page=1&high_quality=1&danmaku=0`}
                title={playingVideo.title}
                allow="autoplay; fullscreen; picture-in-picture"
                allowFullScreen
              />
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
