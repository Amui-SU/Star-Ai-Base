import type {
  VideoNoteAiResultSource,
  VideoNoteBlock,
  VideoNoteBlockType,
} from "@/lib/api";

export type VideoNoteAiAction = "summary" | "questions" | "timestamps";

interface VideoNoteAiTarget {
  blockIds: string[];
  blockTypes: VideoNoteBlockType[];
  label: string;
}

export interface VideoNoteAiResultMeta {
  badge: string;
  source: VideoNoteAiResultSource;
  className: VideoNoteAiResultSource;
  detail: string;
}

const ACTION_TARGETS: Record<VideoNoteAiAction, VideoNoteAiTarget[]> = {
  summary: [
    {
      blockIds: ["ai-summary"],
      blockTypes: ["ai_summary", "ai-summary"],
      label: "摘要",
    },
    {
      blockIds: ["key-points"],
      blockTypes: ["key_points", "key-points"],
      label: "关键观点",
    },
  ],
  questions: [
    {
      blockIds: ["questions", "ai-review-questions"],
      blockTypes: ["questions"],
      label: "复盘问题",
    },
  ],
  timestamps: [
    {
      blockIds: ["timestamp-outline"],
      blockTypes: ["timestamp_outline", "timestamp-outline"],
      label: "时间戳提纲",
    },
  ],
};

export const VIDEO_NOTE_AI_RESULT_META: Record<
  VideoNoteAiResultSource,
  VideoNoteAiResultMeta
> = {
  ai: {
    badge: "AI 生成",
    source: "ai",
    className: "ai",
    detail: "由 AI 模型生成",
  },
  official: {
    badge: "官方章节",
    source: "official",
    className: "official",
    detail: "根据 B 站官方章节整理",
  },
  fallback: {
    badge: "智能兜底",
    source: "fallback",
    className: "fallback",
    detail: "未使用 AI 模型，结果来自已有资料或规则整理，请核对",
  },
};

function hasNonEmptyContent(block: VideoNoteBlock) {
  if (block.text?.trim()) return true;
  return Boolean(
    block.items?.some((item) => item.text?.trim() || item.content?.trim()),
  );
}

export function getVideoNoteAiOverwriteTargets(
  blocks: VideoNoteBlock[],
  action: VideoNoteAiAction,
) {
  return ACTION_TARGETS[action]
    .filter((target) =>
      blocks.some(
        (block) =>
          (target.blockIds.includes(block.id) ||
            target.blockTypes.includes(block.type)) &&
          hasNonEmptyContent(block),
      ),
    )
    .map((target) => target.label);
}
