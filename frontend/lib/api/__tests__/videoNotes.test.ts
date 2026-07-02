import { afterEach, describe, expect, it, vi } from "vitest";
import { importApiForLocation, resetApiTestEnvironment } from "./apiTestUtils";

afterEach(resetApiTestEnvironment);

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("video note API", () => {
  it("wraps list, detail, create, save, export, and AI endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ knowledge_base_id: 7, items: [] }))
      .mockResolvedValueOnce(
        jsonResponse({
          note: null,
          video: {
            bvid: "BVNOTE123",
            title: "AI 视频学习法",
            url: "https://www.bilibili.com/video/BVNOTE123",
          },
          can_create: true,
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ id: 9, bvid: "BVNOTE123" }))
      .mockResolvedValueOnce(jsonResponse({ id: 9, title: "复盘" }))
      .mockResolvedValueOnce(
        jsonResponse({ filename: "复盘.md", markdown: "# 复盘\n" }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          operations: [{ kind: "replace_or_insert_block" }],
          tag_suggestions: ["AI"],
          message: "ok",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          operations: [{ kind: "insert_block" }],
          tag_suggestions: [],
          message: "ok",
        }),
      );
    globalThis.fetch = fetchMock;

    const api = await importApiForLocation({
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost:3000",
    });

    await expect(
      api.videoNoteApi.list({
        knowledgeBaseId: 7,
        q: "学习",
        tag: "AI",
        includeBodySearch: true,
      }),
    ).resolves.toEqual({ knowledge_base_id: 7, items: [] });
    await expect(api.videoNoteApi.detail(7, "BVNOTE123")).resolves.toMatchObject({
      can_create: true,
    });
    await expect(
      api.videoNoteApi.create({
        knowledge_base_id: 7,
        bvid: "BVNOTE123",
        template_id: "standard",
      }),
    ).resolves.toMatchObject({ id: 9 });
    await expect(
      api.videoNoteApi.save(9, {
        title: "复盘",
        blocks: [{ id: "p1", type: "paragraph", text: "hello" }],
        tags: ["AI"],
      }),
    ).resolves.toMatchObject({ title: "复盘" });
    await expect(api.videoNoteApi.exportMarkdown(9)).resolves.toMatchObject({
      filename: "复盘.md",
    });
    await expect(api.videoNoteApi.generateSummary(9)).resolves.toMatchObject({
      tag_suggestions: ["AI"],
    });
    await expect(
      api.videoNoteApi.aiEdit(9, {
        action: "generate_questions",
        instruction: "生成问题",
        selected_block_ids: [],
      }),
    ).resolves.toMatchObject({ operations: [{ kind: "insert_block" }] });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/video-notes?knowledge_base_id=7&q=%E5%AD%A6%E4%B9%A0&tag=AI&include_body_search=true",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/video-notes/7/BVNOTE123",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/video-notes",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          knowledge_base_id: 7,
          bvid: "BVNOTE123",
          template_id: "standard",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://localhost:8000/video-notes/9",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://localhost:8000/video-notes/9/export/markdown",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "http://localhost:8000/video-notes/9/generate-summary",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "http://localhost:8000/video-notes/9/ai-edit",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          action: "generate_questions",
          instruction: "生成问题",
          selected_block_ids: [],
        }),
      }),
    );
  });
});
