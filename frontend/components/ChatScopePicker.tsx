"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type {
  KnowledgeScopeOptions,
  KnowledgeScopeVideo,
  WebSearchProvider,
} from "@/lib/api";
import {
  EMPTY_CHAT_SCOPE,
  type ChatScopeSelection,
  normalizeScope,
  scopeSummary,
} from "@/lib/chatScope";

interface Props {
  options: KnowledgeScopeOptions;
  value: ChatScopeSelection;
  onChange: (next: ChatScopeSelection) => void;
  webSearchEnabled: boolean;
  onWebSearchChange: (enabled: boolean) => void;
  webSearchProvider: WebSearchProvider;
  onWebSearchProviderChange: (provider: WebSearchProvider) => void;
  tavilyConfigured: boolean;
  canConfigureWebSearch?: boolean;
  onConfigureTavily: () => void;
  webSearchNotice?: string;
  disabled?: boolean;
}

function toggleNumber(values: readonly number[], value: number) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

function toggleString(values: readonly string[], value: string) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

export default function ChatScopePicker({
  options,
  value,
  onChange,
  webSearchEnabled,
  onWebSearchChange,
  webSearchProvider,
  onWebSearchProviderChange,
  tavilyConfigured,
  canConfigureWebSearch = false,
  onConfigureTavily,
  webSearchNotice = "",
  disabled = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const rootRef = useRef<HTMLDivElement>(null);
  const normalized = normalizeScope(value);
  const summary = scopeSummary(value);
  const triggerSummary = webSearchNotice && !open ? webSearchNotice : summary;
  const accessibleSummary = webSearchNotice
    ? `${summary}，${webSearchNotice}`
    : webSearchEnabled
      ? `${summary}，联网搜索已开启`
      : summary;

  const allVideos = useMemo(() => {
    const seen = new Set<string>();
    const result: Array<KnowledgeScopeVideo & { folderTitle: string }> = [];
    for (const folder of options.folders) {
      for (const video of folder.videos) {
        if (seen.has(video.bvid)) continue;
        seen.add(video.bvid);
        result.push({ ...video, folderTitle: folder.title });
      }
    }
    return result;
  }, [options.folders]);

  const filteredVideos = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return allVideos;
    return allVideos.filter(
      (video) =>
        video.title.toLowerCase().includes(term) ||
        video.bvid.toLowerCase().includes(term) ||
        video.folderTitle.toLowerCase().includes(term),
    );
  }, [allVideos, query]);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const emit = (next: ChatScopeSelection) => {
    onChange(normalizeScope(next));
  };

  const toggleFolder = (mediaId: number) => {
    emit({
      folderIds: toggleNumber(normalized.folderIds, mediaId),
      bvids: normalized.bvids,
    });
  };

  const toggleVideo = (bvid: string) => {
    emit({
      folderIds: normalized.folderIds,
      bvids: toggleString(normalized.bvids, bvid),
    });
  };

  const toggleExpanded = (mediaId: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(mediaId)) {
        next.delete(mediaId);
      } else {
        next.add(mediaId);
      }
      return next;
    });
  };

  const toggleWebSearch = () => {
    onWebSearchChange(!webSearchEnabled);
    setOpen(false);
  };

  const chooseWebSearchProvider = (provider: WebSearchProvider) => {
    onWebSearchProviderChange(provider);
  };

  const renderVideoOption = (
    video: KnowledgeScopeVideo & { folderTitle?: string },
  ) => (
    <label key={video.bvid} className="scope-option scope-video-option">
      <input
        type="checkbox"
        checked={normalized.bvids.includes(video.bvid)}
        onChange={() => toggleVideo(video.bvid)}
        aria-label={video.title}
      />
      <span className="min-w-0">
        <span className="scope-option-title">{video.title}</span>
        <span className="scope-option-subtitle">
          {video.folderTitle ? `${video.folderTitle} · ` : ""}
          {video.bvid}
        </span>
      </span>
    </label>
  );

  return (
    <div className="scope-picker" ref={rootRef}>
      <button
        type="button"
        className={`mode-chip scope-picker-trigger ${
          webSearchEnabled ? "web-search-enabled" : ""
        } ${webSearchNotice ? "web-search-notice" : ""}`}
        disabled={disabled}
        onClick={() => setOpen((next) => !next)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`提问范围：${accessibleSummary}`}
        title={`提问范围：${accessibleSummary}`}
      >
        <span aria-hidden="true">◎</span>
        <span className="scope-picker-summary">{triggerSummary}</span>
      </button>

      {open && (
        <div
          className="scope-picker-popover"
          role="dialog"
          aria-label="提问范围"
        >
          <div className="scope-picker-head">
            <div>
              <div className="scope-picker-title">提问范围</div>
              <div className="scope-picker-subtitle">{summary}</div>
            </div>
            <button
              type="button"
              className={`scope-web-search-btn ${
                webSearchEnabled ? "active" : ""
              }`}
              aria-label="联网搜索"
              aria-describedby="scope-web-search-privacy"
              aria-pressed={webSearchEnabled}
              title="开启后，模型可能向外部搜索服务发送查询并读取公开网页"
              onClick={toggleWebSearch}
            >
              <span className="scope-web-dot" aria-hidden="true" />
              联网搜索
            </button>
            <span
              id="scope-web-search-privacy"
              className="scope-visually-hidden"
            >
              开启后，模型可能向外部搜索服务发送查询并读取公开网页
            </span>
          </div>

          {webSearchEnabled && (
            <div className="scope-web-provider-panel">
              <div
                className="scope-web-provider-options"
                role="group"
                aria-label="联网搜索方式"
              >
                {(
                  [
                    ["auto", "自动"],
                    ["tavily", "Tavily"],
                    ["html", "内置"],
                  ] as const
                ).map(([provider, label]) => (
                  <button
                    key={provider}
                    type="button"
                    className={`scope-web-provider-option ${
                      webSearchProvider === provider ? "active" : ""
                    }`}
                    aria-pressed={webSearchProvider === provider}
                    disabled={
                      provider === "tavily" &&
                      !tavilyConfigured &&
                      !canConfigureWebSearch
                    }
                    title={
                      provider === "tavily" &&
                      !tavilyConfigured &&
                      !canConfigureWebSearch
                        ? "Tavily 需要管理员配置"
                        : undefined
                    }
                    onClick={() => chooseWebSearchProvider(provider)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {!tavilyConfigured && !canConfigureWebSearch && (
                <div className="scope-web-config-note">
                  Tavily 需要管理员配置
                </div>
              )}
              {webSearchProvider === "tavily" &&
                !tavilyConfigured &&
                canConfigureWebSearch && (
                  <button
                    type="button"
                    className="scope-web-config-btn"
                    onClick={onConfigureTavily}
                  >
                    配置 Tavily
                  </button>
                )}
            </div>
          )}

          <div className="scope-mode-grid" aria-label="范围类型">
            <button
              type="button"
              aria-label="整个知识库"
              className={`scope-mode-card ${
                normalized.folderIds.length === 0 &&
                normalized.bvids.length === 0
                  ? "active"
                  : ""
              }`}
              onClick={() => emit(EMPTY_CHAT_SCOPE)}
            >
              <span className="scope-mode-icon">◎</span>
              <span>
                <span className="scope-mode-title">整个知识库</span>
                <span className="scope-mode-copy">默认检索全部已入库内容</span>
              </span>
            </button>
            <div className="scope-mode-card passive">
              <span className="scope-mode-icon">□</span>
              <span>
                <span className="scope-mode-title">收藏夹</span>
                <span className="scope-mode-copy">勾选一个或多个收藏夹</span>
              </span>
            </div>
            <div className="scope-mode-card passive">
              <span className="scope-mode-icon">◇</span>
              <span>
                <span className="scope-mode-title">单个视频</span>
                <span className="scope-mode-copy">搜索后精确加入问题范围</span>
              </span>
            </div>
          </div>

          <div className="scope-section">
            <div className="scope-section-title">收藏夹</div>
            {options.folders.length === 0 ? (
              <div className="scope-empty">当前知识库暂无可选范围</div>
            ) : (
              options.folders.map((folder) => {
                const isExpanded = expanded.has(folder.media_id);
                const canExpand = folder.videos.length > 0;
                return (
                  <div key={folder.media_id} className="scope-folder">
                    <div className="scope-folder-row">
                      <label className="scope-option scope-folder-option">
                        <input
                          type="checkbox"
                          checked={normalized.folderIds.includes(
                            folder.media_id,
                          )}
                          onChange={() => toggleFolder(folder.media_id)}
                          aria-label={folder.title}
                        />
                        <span className="min-w-0">
                          <span className="scope-option-title">
                            {folder.title}
                          </span>
                          <span className="scope-option-subtitle">
                            {folder.video_count} 个已入库视频
                          </span>
                        </span>
                      </label>
                      <button
                        type="button"
                        className="scope-expand-btn"
                        disabled={!canExpand}
                        onClick={() =>
                          canExpand && toggleExpanded(folder.media_id)
                        }
                        aria-expanded={isExpanded}
                        aria-label={`${isExpanded ? "收起" : "展开"} ${folder.title}`}
                      >
                        ›
                      </button>
                    </div>
                    {isExpanded && canExpand && (
                      <div className="scope-folder-videos">
                        {folder.videos.map((video) =>
                          renderVideoOption({
                            ...video,
                            folderTitle: folder.title,
                          }),
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          <div className="scope-section">
            <label className="scope-section-title" htmlFor="scope-video-search">
              单独选择视频
            </label>
            <input
              id="scope-video-search"
              className="scope-search-input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索视频标题或 BV 号"
              aria-label="搜索视频"
            />
            <div className="scope-video-list">
              {filteredVideos.length > 0 ? (
                filteredVideos.map(renderVideoOption)
              ) : (
                <div className="scope-empty">没有匹配的视频</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
