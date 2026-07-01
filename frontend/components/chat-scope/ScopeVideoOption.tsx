"use client";

import type { KnowledgeScopeVideo } from "@/lib/api";
import { displayFolderTitle, displayVideoTitle } from "@/lib/displayNames";

export type ScopeVideoOptionItem = KnowledgeScopeVideo & {
  folderTitle?: string;
};

interface ScopeVideoOptionProps {
  video: ScopeVideoOptionItem;
  selected: boolean;
  onToggleVideo: (bvid: string) => void;
}

export default function ScopeVideoOption({
  video,
  selected,
  onToggleVideo,
}: ScopeVideoOptionProps) {
  const videoTitle = displayVideoTitle(video.title);
  const folderTitle = video.folderTitle
    ? displayFolderTitle(video.folderTitle)
    : "";

  return (
    <label className="scope-option scope-video-option">
      <input
        type="checkbox"
        checked={selected}
        onChange={() => onToggleVideo(video.bvid)}
        aria-label={videoTitle}
      />
      <span className="min-w-0">
        <span className="scope-option-title">{videoTitle}</span>
        <span className="scope-option-subtitle">
          {folderTitle ? `${folderTitle} · ` : ""}
          {video.bvid}
        </span>
      </span>
    </label>
  );
}
