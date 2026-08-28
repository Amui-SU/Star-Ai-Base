import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { knowledgeBaseApi } from "@/lib/api";
import { useChatKnowledgeContext } from "./useChatKnowledgeContext";

vi.mock("@/lib/api", () => ({
  knowledgeBaseApi: { stats: vi.fn(), getScopeOptions: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("reloads statistics and scope options on content refresh without resetting chat", async () => {
  const actionsRef = {
    current: {
      onMessagesClear: vi.fn(),
      onResetConversationIdentity: vi.fn(),
      onResetChat: vi.fn(),
      onStopGenerating: vi.fn(),
      onWebSearchEnabledChange: vi.fn(),
      onWebSearchNoticeClear: vi.fn(),
    },
  };
  vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
    knowledge_base_id: 7,
    workspace_id: 1,
    total_videos: 0,
    folders: [],
    scoped: true,
  });
  vi.mocked(knowledgeBaseApi.getScopeOptions).mockResolvedValue({
    folders: [],
  });
  const { result, rerender } = renderHook(
    ({ statsKey }) =>
      useChatKnowledgeContext({
        actionsRef,
        knowledgeBaseId: 7,
        statsKey,
      }),
    { initialProps: { statsKey: 0 } },
  );
  await waitFor(() => expect(result.current.stats?.total_videos).toBe(0));
  act(() => result.current.setChatScope({ folder_ids: [10], bvids: [] }));
  vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
    knowledge_base_id: 7,
    workspace_id: 1,
    total_videos: 1,
    folders: [],
    scoped: true,
  });
  vi.mocked(knowledgeBaseApi.getScopeOptions).mockResolvedValue({
    folders: [
      {
        media_id: 10,
        title: "新导入",
        video_count: 1,
        videos: [{ bvid: "BVnew", title: "新视频" }],
      },
    ],
  });
  rerender({ statsKey: 1 });
  await waitFor(() =>
    expect(result.current.scopeOptions.folders[0]?.title).toBe("新导入"),
  );
  expect(result.current.stats?.total_videos).toBe(1);
  expect(result.current.chatScope).toEqual({ folder_ids: [10], bvids: [] });
  expect(actionsRef.current.onResetChat).toHaveBeenCalledTimes(1);
  expect(actionsRef.current.onResetConversationIdentity).toHaveBeenCalledTimes(
    1,
  );
});
