"use client";

import type { VideoNoteTemplateId, VideoNoteVideo } from "@/lib/api";

interface VideoNoteTemplatePickerProps {
  video: VideoNoteVideo;
  creating: boolean;
  onCreate: (templateId: VideoNoteTemplateId) => void;
}

export default function VideoNoteTemplatePicker({
  video,
  creating,
  onCreate,
}: VideoNoteTemplatePickerProps) {
  return (
    <div className="video-note-template-picker">
      <div>
        <span className="video-note-kicker">创建笔记</span>
        <h3>{video.title}</h3>
      </div>
      <div className="video-note-template-grid">
        <button
          type="button"
          onClick={() => onCreate("standard")}
          disabled={creating}
        >
          <strong>标准模板</strong>
          <span>摘要、关键观点、时间戳、我的笔记</span>
        </button>
        <button
          type="button"
          onClick={() => onCreate("blank")}
          disabled={creating}
        >
          <strong>空白笔记</strong>
          <span>从一张空白页开始</span>
        </button>
      </div>
    </div>
  );
}
