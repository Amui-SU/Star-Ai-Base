"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import ChatScopeTrigger from "@/components/chat-scope/ChatScopeTrigger";
import ScopeFolderSection from "@/components/chat-scope/ScopeFolderSection";
import ScopeModeGrid from "@/components/chat-scope/ScopeModeGrid";
import ScopeVideoSearchSection from "@/components/chat-scope/ScopeVideoSearchSection";
import ScopeWebSearchPanel from "@/components/chat-scope/ScopeWebSearchPanel";
import type { ScopeVideoOptionItem } from "@/components/chat-scope/ScopeVideoOption";
import type { KnowledgeScopeOptions, WebSearchProvider } from "@/lib/api";
import {
  EMPTY_CHAT_SCOPE,
  type ChatScopeSelection,
  normalizeScope,
  scopeSummary,
} from "@/lib/chatScope";
import { displayFolderTitle, displayVideoTitle } from "@/lib/displayNames";

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
    const result: Array<ScopeVideoOptionItem & { folderTitle: string }> = [];
    for (const folder of options.folders) {
      const folderTitle = displayFolderTitle(folder.title);
      for (const video of folder.videos) {
        if (seen.has(video.bvid)) continue;
        seen.add(video.bvid);
        result.push({
          ...video,
          title: displayVideoTitle(video.title),
          folderTitle,
        });
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

  return (
    <div className="scope-picker" ref={rootRef}>
      <ChatScopeTrigger
        open={open}
        disabled={disabled}
        webSearchEnabled={webSearchEnabled}
        webSearchNotice={webSearchNotice}
        triggerSummary={triggerSummary}
        accessibleSummary={accessibleSummary}
        onToggleOpen={() => setOpen((next) => !next)}
      />

      {open && (
        <div
          className="scope-picker-popover"
          role="dialog"
          aria-label="提问范围"
        >
          <ScopeWebSearchPanel
            summary={summary}
            webSearchEnabled={webSearchEnabled}
            webSearchProvider={webSearchProvider}
            tavilyConfigured={tavilyConfigured}
            canConfigureWebSearch={canConfigureWebSearch}
            onToggleWebSearch={toggleWebSearch}
            onWebSearchProviderChange={onWebSearchProviderChange}
            onConfigureTavily={onConfigureTavily}
          />

          <ScopeModeGrid
            wholeKnowledgeBaseActive={
              normalized.folderIds.length === 0 && normalized.bvids.length === 0
            }
            onSelectWholeKnowledgeBase={() => emit(EMPTY_CHAT_SCOPE)}
          />

          <ScopeFolderSection
            folders={options.folders}
            expandedFolderIds={expanded}
            selectedFolderIds={normalized.folderIds}
            selectedBvids={normalized.bvids}
            onToggleFolder={toggleFolder}
            onToggleExpanded={toggleExpanded}
            onToggleVideo={toggleVideo}
          />

          <ScopeVideoSearchSection
            query={query}
            videos={filteredVideos}
            selectedBvids={normalized.bvids}
            onQueryChange={setQuery}
            onToggleVideo={toggleVideo}
          />
        </div>
      )}
    </div>
  );
}
