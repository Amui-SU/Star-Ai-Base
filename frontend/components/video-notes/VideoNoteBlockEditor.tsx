"use client";

import type { VideoNoteBlock as VideoNoteBlockData } from "@/lib/api";
import {
  addVideoNoteBlock,
  convertVideoNoteBlock,
  createVideoNoteBlock,
  moveVideoNoteBlock,
  removeVideoNoteBlock,
  updateVideoNoteBlock,
} from "./videoNoteBlocks";
import VideoNoteBlock from "./VideoNoteBlock";

interface VideoNoteBlockEditorProps {
  blocks: VideoNoteBlockData[];
  onChange: (blocks: VideoNoteBlockData[]) => void;
}

export default function VideoNoteBlockEditor({
  blocks,
  onChange,
}: VideoNoteBlockEditorProps) {
  return (
    <div className="video-note-block-editor">
      <div className="video-note-editor-actions">
        <button
          type="button"
          onClick={() =>
            onChange(addVideoNoteBlock(blocks, createVideoNoteBlock("paragraph")))
          }
        >
          添加段落
        </button>
        <button
          type="button"
          onClick={() =>
            onChange(addVideoNoteBlock(blocks, createVideoNoteBlock("todo")))
          }
        >
          添加待办
        </button>
      </div>
      <div className="video-note-block-list">
        {blocks.map((block) => (
          <VideoNoteBlock
            key={block.id}
            block={block}
            onChange={(patch) =>
              onChange(updateVideoNoteBlock(blocks, block.id, patch))
            }
            onConvert={(type) =>
              onChange(convertVideoNoteBlock(blocks, block.id, type))
            }
            onMoveDown={() =>
              onChange(moveVideoNoteBlock(blocks, block.id, "down"))
            }
            onMoveUp={() => onChange(moveVideoNoteBlock(blocks, block.id, "up"))}
            onRemove={() => onChange(removeVideoNoteBlock(blocks, block.id))}
          />
        ))}
      </div>
    </div>
  );
}
