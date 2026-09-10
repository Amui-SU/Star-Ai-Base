import { describe, expect, it } from "vitest";

import {
  VIDEO_NOTE_AI_RESULT_META,
  getVideoNoteAiOverwriteTargets,
} from "./videoNoteAiUi";

describe("getVideoNoteAiOverwriteTargets", () => {
  it("maps each AI action to the content sections it can overwrite", () => {
    const blocks = [
      { id: "summary", type: "ai_summary", text: "现有摘要" },
      {
        id: "points",
        type: "key_points",
        items: [{ text: "现有观点" }],
      },
      {
        id: "questions",
        type: "questions",
        items: [{ content: "现有问题" }],
      },
      {
        id: "timestamps",
        type: "timestamp_outline",
        items: [{ text: "现有时间戳" }],
      },
    ];

    expect(getVideoNoteAiOverwriteTargets(blocks, "summary")).toEqual([
      "摘要",
      "关键观点",
    ]);
    expect(getVideoNoteAiOverwriteTargets(blocks, "questions")).toEqual([
      "复盘问题",
    ]);
    expect(getVideoNoteAiOverwriteTargets(blocks, "timestamps")).toEqual([
      "时间戳提纲",
    ]);
  });

  it("does not require confirmation for missing or whitespace-only targets", () => {
    const blocks = [
      { id: "summary", type: "ai_summary", text: "   " },
      {
        id: "points",
        type: "key_points",
        items: [{ text: "\n" }, { content: "\t" }],
      },
      { id: "questions", type: "questions", items: [] },
    ];

    expect(getVideoNoteAiOverwriteTargets(blocks, "summary")).toEqual([]);
    expect(getVideoNoteAiOverwriteTargets(blocks, "questions")).toEqual([]);
    expect(getVideoNoteAiOverwriteTargets(blocks, "timestamps")).toEqual([]);
  });

  it("recognizes the hyphenated target names used by the UI contract", () => {
    const blocks = [
      { id: "summary", type: "ai-summary", text: "现有摘要" },
      { id: "points", type: "key-points", text: "现有观点" },
      { id: "timestamps", type: "timestamp-outline", text: "现有提纲" },
    ];

    expect(getVideoNoteAiOverwriteTargets(blocks, "summary")).toEqual([
      "摘要",
      "关键观点",
    ]);
    expect(getVideoNoteAiOverwriteTargets(blocks, "timestamps")).toEqual([
      "时间戳提纲",
    ]);
  });

  it("recognizes stable AI block ids after Markdown changes their types", () => {
    const blocks = [
      { id: "ai-summary", type: "paragraph", text: "往返后的摘要" },
      {
        id: "key-points",
        type: "bulleted_list",
        items: [{ text: "往返后的观点" }],
      },
      {
        id: "questions",
        type: "bulleted_list",
        items: [{ text: "往返后的问题" }],
      },
      {
        id: "timestamp-outline",
        type: "bulleted_list",
        items: [{ text: "往返后的时间戳" }],
      },
      { id: "ordinary", type: "paragraph", text: "普通正文" },
    ];

    expect(getVideoNoteAiOverwriteTargets(blocks, "summary")).toEqual([
      "摘要",
      "关键观点",
    ]);
    expect(getVideoNoteAiOverwriteTargets(blocks, "questions")).toEqual([
      "复盘问题",
    ]);
    expect(getVideoNoteAiOverwriteTargets(blocks, "timestamps")).toEqual([
      "时间戳提纲",
    ]);
  });
});

describe("VIDEO_NOTE_AI_RESULT_META", () => {
  it("describes AI, official, and fallback result sources", () => {
    expect(VIDEO_NOTE_AI_RESULT_META).toEqual({
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
    });
  });
});
