"use client";

import { createPortal } from "react-dom";

export interface PlayingVideo {
  bvid: string;
  title: string;
}

interface VideoPlayerPortalProps {
  video: PlayingVideo | null;
  onClose: () => void;
}

export default function VideoPlayerPortal({
  video,
  onClose,
}: VideoPlayerPortalProps) {
  if (!video || typeof document === "undefined") return null;

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card video-player-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="video-player-header">
          <div className="video-player-title truncate" title={video.title}>
            {video.title}
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onClose}
            title="关闭"
          >
            关闭
          </button>
        </div>
        <iframe
          className="video-player-frame"
          src={`https://player.bilibili.com/player.html?bvid=${video.bvid}&page=1&high_quality=1&danmaku=0`}
          title={video.title}
          allow="autoplay; fullscreen; picture-in-picture"
          allowFullScreen
        />
      </div>
    </div>,
    document.body,
  );
}
