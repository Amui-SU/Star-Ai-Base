"use client";

import type { VideoNoteBlock as VideoNoteBlockData } from "@/lib/api";
import VideoNoteBlockToolbar from "./VideoNoteBlockToolbar";

interface VideoNoteBlockProps {
  block: VideoNoteBlockData;
  onChange: (patch: Partial<VideoNoteBlockData>) => void;
  onConvert: (type: VideoNoteBlockData["type"]) => void;
  onMoveDown: () => void;
  onMoveUp: () => void;
  onRemove: () => void;
}

function itemText(block: VideoNoteBlockData): string {
  return (block.items ?? [])
    .map((item) => item.text ?? item.content ?? "")
    .filter(Boolean)
    .join("\n");
}

function parseItems(value: string) {
  return value
    .split("\n")
    .map((text) => text.trim())
    .filter(Boolean)
    .map((text) => ({ text }));
}

export default function VideoNoteBlock({
  block,
  onChange,
  onConvert,
  onMoveDown,
  onMoveUp,
  onRemove,
}: VideoNoteBlockProps) {
  const multiline = [
    "paragraph",
    "ai_summary",
    "quote",
    "key_points",
    "questions",
    "timestamp_outline",
    "bulleted_list",
  ].includes(block.type);
  const value = block.items ? itemText(block) : (block.text ?? "");

  return (
    <div className={`video-note-block video-note-block-${block.type}`}>
      <VideoNoteBlockToolbar
        block={block}
        onConvert={onConvert}
        onMoveDown={onMoveDown}
        onMoveUp={onMoveUp}
        onRemove={onRemove}
      />
      {block.type === "todo" ? (
        <label className="video-note-todo">
          <input
            type="checkbox"
            checked={Boolean(block.checked)}
            onChange={(event) => onChange({ checked: event.target.checked })}
          />
          <input
            aria-label={`编辑块 ${block.id}`}
            value={block.text ?? ""}
            onChange={(event) => onChange({ text: event.target.value })}
          />
        </label>
      ) : multiline ? (
        <textarea
          aria-label={`编辑块 ${block.id}`}
          value={value}
          onChange={(event) => {
            if (block.items) {
              onChange({ items: parseItems(event.target.value) });
            } else {
              onChange({ text: event.target.value });
            }
          }}
          rows={block.type === "heading" ? 1 : 4}
        />
      ) : (
        <input
          aria-label={`编辑块 ${block.id}`}
          value={block.text ?? ""}
          onChange={(event) => onChange({ text: event.target.value })}
        />
      )}
    </div>
  );
}
