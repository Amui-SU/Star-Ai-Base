import { afterEach, describe, expect, it, vi } from "vitest";
import { importApiForLocation, resetApiTestEnvironment } from "./apiTestUtils";

afterEach(resetApiTestEnvironment);

describe("import API uploads", () => {
  it("uploads local videos with FormData and no JSON content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          status: "pending",
          source_type: "local_video",
          message: "已创建本地视频导入任务",
          task_id: "task-local",
          bvid: "LV123",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const api = await importApiForLocation({
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost:3000",
    });
    const file = new File(["video"], "demo.mp4", { type: "video/mp4" });

    await expect(
      api.importApi.importLocalVideo({
        file,
        knowledge_base_id: 7,
        title: "demo.mp4",
      }),
    ).resolves.toMatchObject({
      source_type: "local_video",
      task_id: "task-local",
    });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8000/imports/local-video",
    );
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers).not.toHaveProperty("Content-Type");
  });
});
