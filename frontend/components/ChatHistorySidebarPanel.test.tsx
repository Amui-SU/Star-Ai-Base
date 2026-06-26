import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChatHistorySidebarPanel from "@/components/ChatHistorySidebarPanel";
import { chatHistoryApi } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    chatHistoryApi: {
      ...actual.chatHistoryApi,
      list: vi.fn(),
    },
  };
});

const conversations = [
  {
    id: 1,
    user_id: 1,
    workspace_id: 1,
    knowledge_base_id: 1,
    title: "今天的 RAG 讨论",
    scope: null,
    web_search: false,
    web_search_provider: "auto" as const,
    message_count: 2,
    created_at: "2026-06-26T02:00:00Z",
    updated_at: "2026-06-26T02:00:00Z",
  },
  {
    id: 2,
    user_id: 1,
    workspace_id: 1,
    knowledge_base_id: 1,
    title: "昨天的地址翻译",
    scope: { folder_ids: [9], bvids: [] },
    web_search: false,
    web_search_provider: "auto" as const,
    message_count: 3,
    created_at: "2026-06-25T02:00:00Z",
    updated_at: "2026-06-25T02:00:00Z",
  },
  {
    id: 3,
    user_id: 1,
    workspace_id: 1,
    knowledge_base_id: 1,
    title: "七天内视频总结",
    scope: { folder_ids: [], bvids: ["BV123"] },
    web_search: false,
    web_search_provider: "auto" as const,
    message_count: 4,
    created_at: "2026-06-22T02:00:00Z",
    updated_at: "2026-06-22T02:00:00Z",
  },
  {
    id: 4,
    user_id: 1,
    workspace_id: 1,
    knowledge_base_id: 1,
    title: "三十天内联网检索",
    scope: null,
    web_search: true,
    web_search_provider: "tavily" as const,
    message_count: 5,
    created_at: "2026-06-01T02:00:00Z",
    updated_at: "2026-06-01T02:00:00Z",
  },
];

describe("ChatHistorySidebarPanel", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-06-26T12:00:00Z"));
    vi.mocked(chatHistoryApi.list).mockResolvedValue({ items: conversations });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("renders a compact history home without the large title", async () => {
    const onNewConversation = vi.fn();
    const onCollapse = vi.fn();
    render(
      <ChatHistorySidebarPanel
        knowledgeBaseId={1}
        onOpenConversation={vi.fn()}
        onNewConversation={onNewConversation}
        onCollapse={onCollapse}
      />,
    );

    await screen.findByText("今天");

    expect(screen.queryByRole("heading", { name: "对话历史" })).toBeNull();
    const newButton = screen.getByRole("button", { name: "开启新对话" });
    expect(newButton).toHaveClass("sidebar-history-new-chat");
    expect(
      newButton.querySelector(".sidebar-history-new-chat-icon"),
    ).toBeInTheDocument();
    expect(newButton.closest(".sidebar-history-topbar")).not.toBeNull();
    await userEvent.click(newButton);
    expect(onNewConversation).toHaveBeenCalled();

    const collapseButton = screen.getByRole("button", { name: "收起展开页" });
    expect(collapseButton).toHaveClass("sidebar-history-collapse");
    expect(collapseButton.closest(".sidebar-history-topbar")).not.toBeNull();
    await userEvent.click(collapseButton);
    expect(onCollapse).toHaveBeenCalled();
  });

  it("groups conversations by recency and shows the scope marker at the end", async () => {
    render(
      <ChatHistorySidebarPanel
        knowledgeBaseId={1}
        onOpenConversation={vi.fn()}
        onNewConversation={vi.fn()}
      />,
    );

    expect(await screen.findByText("今天")).toBeVisible();
    expect(screen.getByText("昨天")).toBeVisible();
    expect(screen.getByText("7 天内")).toBeVisible();
    expect(screen.getByText("30 天内")).toBeVisible();

    const todayRow = screen.getByRole("button", { name: /今天的 RAG 讨论/ });
    expect(within(todayRow).getByText("当前知识库")).toHaveClass(
      "sidebar-history-scope",
    );
    const folderRow = screen.getByRole("button", {
      name: /昨天的地址翻译/,
    });
    expect(within(folderRow).getByText("文件夹范围")).toHaveClass(
      "sidebar-history-scope",
    );
    const videoRow = screen.getByRole("button", { name: /七天内视频总结/ });
    expect(within(videoRow).getByText("视频范围")).toHaveClass(
      "sidebar-history-scope",
    );
    const webRow = screen.getByRole("button", { name: /三十天内联网检索/ });
    expect(within(webRow).getByText("联网")).toHaveClass(
      "sidebar-history-scope",
    );
  });

  it("opens search from the top-right and filters conversations", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <ChatHistorySidebarPanel
        knowledgeBaseId={1}
        onOpenConversation={vi.fn()}
        onNewConversation={vi.fn()}
      />,
    );

    await screen.findByText("今天的 RAG 讨论");
    await user.click(screen.getByRole("button", { name: "检索对话" }));
    await user.type(screen.getByPlaceholderText("检索对话"), "联网");

    await waitFor(() => {
      expect(screen.getByText("三十天内联网检索")).toBeVisible();
    });
    expect(screen.queryByText("今天的 RAG 讨论")).toBeNull();
  });
});
