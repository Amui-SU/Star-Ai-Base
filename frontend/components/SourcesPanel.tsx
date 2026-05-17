"use client";

import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  FavoriteFolder,
  Video,
  favoritesApi,
  knowledgeApi,
  BuildStatus,
  FolderStatus,
  OrganizePreviewResponse,
} from "@/lib/api";
import OrganizePreviewModal from "@/components/OrganizePreviewModal";

interface Props {
  sessionId: string;
  onBuildDone?: () => void;
  onSelectionChange?: (folderIds: number[]) => void;
}

export default function SourcesPanel({ sessionId, onBuildDone, onSelectionChange }: Props) {
  const [folders, setFolders] = useState<(FavoriteFolder & { videos?: Video[]; expanded?: boolean; loading?: boolean; count_source?: "bili" | "filtered" | "db" })[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [customVideoNames, setCustomVideoNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [progress, setProgress] = useState<BuildStatus | null>(null);
  const [statusMap, setStatusMap] = useState<Record<number, FolderStatus>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [organizeOpen, setOrganizeOpen] = useState(false);
  const [organizeLoading, setOrganizeLoading] = useState(false);
  const [organizePreview, setOrganizePreview] = useState<OrganizePreviewResponse | null>(null);
  const [organizeMessage, setOrganizeMessage] = useState<string | null>(null);
  const [playingVideo, setPlayingVideo] = useState<{ bvid: string; title: string } | null>(null);

  // 加载收藏夹列表（从B站获取）
  const loadFolders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await favoritesApi.getList(sessionId);
      setFolders(data.map((f) => ({ ...f, count_source: "bili" })));
      setMessage(null);
    } catch (err) {
      setFolders([]);
      setMessage(err instanceof Error ? err.message : "加载收藏夹失败，请稍后重试");
    }
    setLoading(false);
  }, [sessionId]);

  // 加载入库状态（从本地数据库）
  const loadStatuses = useCallback(async () => {
    try {
      const data = await knowledgeApi.getFolderStatus(sessionId);
      const map: Record<number, FolderStatus> = {};
      data.forEach((item) => {
        map[item.media_id] = item;
      });
      setStatusMap(map);
      setFolders((prev) =>
        prev.map((f) => {
          const s = map[f.media_id];
          if (!s?.media_count) return f;
          if (f.count_source === "filtered") return f;
          return { ...f, count_source: "bili" };
        })
      );
    } catch {
      // 状态接口失败不影响主列表展示
    }
  }, [sessionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadFolders().then(loadStatuses);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadFolders, loadStatuses]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const raw = localStorage.getItem("custom_video_names");
        if (raw) {
          const parsed = JSON.parse(raw) as Record<string, string>;
          setCustomVideoNames(parsed || {});
        }
      } catch {
        // 忽略本地解析异常
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const saveCustomNames = (next: Record<string, string>) => {
    setCustomVideoNames(next);
    try {
      localStorage.setItem("custom_video_names", JSON.stringify(next));
    } catch {
      // 忽略本地存储异常
    }
  };

  const renameVideo = (video: Video) => {
    const current = customVideoNames[video.bvid] || video.title;
    const nextName = window.prompt("请输入自定义视频名称", current);
    if (nextName === null) return;
    const trimmed = nextName.trim();
    const nextMap = { ...customVideoNames };
    if (!trimmed || trimmed === video.title) {
      delete nextMap[video.bvid];
    } else {
      nextMap[video.bvid] = trimmed;
    }
    saveCustomNames(nextMap);
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
      const res = await favoritesApi.organizePreview(folderId, sessionId);
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
      })
    );

    const folder = folders.find((f) => f.media_id === id);
    if (!folder?.videos) {
      try {
        const res = await favoritesApi.getAllVideos(id, sessionId);
        setFolders((prev) =>
          prev.map((f) =>
            f.media_id === id ? { ...f, videos: res.videos, loading: false, media_count: res.total, count_source: "filtered" } : f
          )
        );
      } catch {
        setFolders((prev) =>
          prev.map((f) => (f.media_id === id ? { ...f, loading: false } : f))
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
    onSelectionChange?.(Array.from(s));
  };

  // 构建/更新知识库（统一操作）
  const buildKnowledge = async () => {
    if (selected.size === 0) return;
    setBuilding(true);
    setMessage(null);
    setProgress(null);

    try {
      const res = await knowledgeApi.build({ folder_ids: Array.from(selected) }, sessionId);

      const poll = async () => {
        const s = await knowledgeApi.getBuildStatus(res.task_id);
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
  const formatTime = (value?: string | null) => {
    if (!value) return null;
    try {
      let dateStr = value;
      if (!value.includes('T') && !value.includes('Z')) {
        dateStr = value.replace(' ', 'T') + 'Z';
      }
      const date = new Date(dateStr);
      if (Number.isNaN(date.getTime())) return null;

      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hour = String(date.getHours()).padStart(2, '0');
      const minute = String(date.getMinutes()).padStart(2, '0');
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
      return { label: "有更新", className: "partial", indexedCount, totalCount };
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
      return `入库 (${selected.size})`;
    }
    return `更新 (${selected.size})`;
  };

  return (
    <div className="panel-inner">
      <div className="panel-header items-start flex-wrap gap-y-2">
        <div className="flex items-center gap-2 ml-1 mt-0.5 min-w-[88px]">
          <div className="w-7 h-7 rounded-lg border border-(--border) bg-[rgba(217,139,43,0.16)] flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-(--accent-strong)" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.9} d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
            </svg>
          </div>
          <div className="flex flex-col items-center justify-center">
            <div className="panel-title whitespace-nowrap text-sm leading-4">收藏夹</div>
            <div className="panel-subtitle text-[11px] leading-4 text-center mt-1">{folders.length} 个</div>
          </div>
        </div>
        <div className="panel-actions ml-auto gap-2">
          <button
            onClick={() => {
              const def = folders.find((f) => f.is_default || f.title === "默认收藏夹");
              if (def) {
                openOrganizePreview(def.media_id);
              } else {
                setOrganizeMessage("未找到默认收藏夹");
              }
            }}
            className="btn btn-ghost btn-sm px-3 whitespace-nowrap"
            title="快速整理默认收藏夹"
            disabled={loading || organizeLoading}
          >
            {organizeLoading ? "整理中..." : "快速整理"}
          </button>
          <button
            onClick={refresh}
            className="btn btn-ghost btn-sm px-0! w-8 h-8"
            disabled={loading}
            title={loading ? "加载中..." : "刷新"}
            aria-label={loading ? "加载中..." : "刷新"}
          >
            <svg className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.9} d="M21 12a9 9 0 11-2.2-5.9l1.7 1.9h-3.1" />
            </svg>
          </button>
        </div>
      </div>

      <div className="panel-body">
        <div className="sources-scroll">
          {loading ? (
            <div className="text-center text-sm text-(--muted) py-6">加载中...</div>
          ) : folders.length === 0 ? (
            <div className="text-center text-sm text-(--muted) py-6">暂无收藏夹</div>
          ) : (
            <div className="space-y-2">
              {folders.map((f) => {
                const status = getFolderStatus(f.media_id, f.media_count);
                const lastSync = formatTime(statusMap[f.media_id]?.last_sync_at);

                return (
                  <div key={f.media_id} className={`folder-card ${selected.has(f.media_id) ? "selected" : ""}`}>
                    <div className="folder-head" onClick={() => toggleExpand(f.media_id)}>
                      <input
                        type="checkbox"
                        checked={selected.has(f.media_id)}
                        onChange={() => toggleSelect(f.media_id)}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`选择收藏夹 ${f.title}`}
                        className="folder-checkbox"
                      />
                      <div className="folder-meta">
                        <div className="folder-title" title={f.title}>{f.title}</div>
                      <div className="folder-count">
                        {status.indexedCount}/{status.totalCount ?? f.media_count} 个视频
                        {lastSync && ` · ${lastSync}`}
                      </div>
                      </div>
                      <span className={`status-pill ${status.className}`}>{status.label}</span>
                      <div className="folder-toggle">
                        <svg className={`w-4 h-4 transition-transform ${f.expanded ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </div>

                    <div className={`folder-list-wrapper ${f.expanded ? "expanded" : ""}`}>
                      <div className="folder-list">
                        {f.loading ? (
                          <div className="text-xs text-(--muted)">加载中...</div>
                        ) : f.videos?.length === 0 ? (
                          <div className="text-xs text-(--muted)">暂无视频</div>
                        ) : (
                          f.videos?.map((v) => (
                            <div
                              key={v.bvid}
                              className="video-item"
                            >
                              <button
                                type="button"
                                className="video-play-btn"
                                onClick={() => setPlayingVideo({ bvid: v.bvid, title: customVideoNames[v.bvid] || v.title })}
                                title="在线播放"
                                aria-label={`播放 ${customVideoNames[v.bvid] || v.title}`}
                              >
                                ▶
                              </button>
                              <button
                                type="button"
                                className="video-rename-btn"
                                title="重命名"
                                aria-label={`重命名 ${customVideoNames[v.bvid] || v.title}`}
                                onClick={() => renameVideo(v)}
                              >
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536M9 11l6.768-6.768a2.5 2.5 0 013.536 0l.232.232a2.5 2.5 0 010 3.536L12.768 14.768A2 2 0 0111.354 15H9v-2.354A2 2 0 019.586 11.939zM5 19h14" />
                                </svg>
                              </button>
                              <a
                                href={`https://www.bilibili.com/video/${v.bvid}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="truncate"
                                aria-label={customVideoNames[v.bvid] || v.title}
                              >
                                {customVideoNames[v.bvid] || v.title}
                              </a>
                            </div>
                          ))
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
              <span className="text-(--muted) truncate">{progress.current_step}</span>
              <span className="text-(--accent)">{progress.progress}%</span>
            </div>
            <div className="progress">
              <div className="progress-bar" style={{ width: `${progress.progress}%` }} />
            </div>
          </div>
        )}

        {/* 消息 */}
        {message && <div className="text-xs text-(--muted) mb-3">{message}</div>}
        {organizeMessage && <div className="text-xs text-(--muted) mb-3">{organizeMessage}</div>}

        {/* 主按钮 */}
        <button
          onClick={buildKnowledge}
          disabled={selected.size === 0 || building}
          className="btn glass-action-btn w-full"
        >
          {getButtonText()}
        </button>

        <p className="text-xs text-(--muted) text-center mt-2">
          入库后可在右侧进行问答
        </p>
      </div>

      <OrganizePreviewModal
        open={organizeOpen}
        sessionId={sessionId}
        preview={organizePreview}
        loading={organizeLoading}
        errorMessage={organizeMessage}
        onClose={() => setOrganizeOpen(false)}
        onApplied={refresh}
      />

      {playingVideo && typeof document !== "undefined" && createPortal(
        <div className="modal-backdrop" onClick={() => setPlayingVideo(null)}>
          <div className="modal-card video-player-modal" onClick={(e) => e.stopPropagation()}>
            <div className="video-player-header">
              <div className="video-player-title truncate" title={playingVideo.title}>
                {playingVideo.title}
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setPlayingVideo(null)} title="关闭">
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
        document.body
      )}
    </div>
  );
}
