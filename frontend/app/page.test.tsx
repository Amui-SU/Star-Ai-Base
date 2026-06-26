import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Home from "@/app/page";
import { chatHistoryApi, sourceBindingApi, systemAuthApi } from "@/lib/api";

const { chatPanelMock } = vi.hoisted(() => ({
  chatPanelMock: vi.fn(),
}));

vi.mock("@/components/AuthPage", () => ({
  default: () => <div>Auth Page</div>,
}));

vi.mock("@/components/UserMenu", () => ({
  default: () => <button type="button">User Menu</button>,
}));

vi.mock("@/components/KnowledgeBasePanel", () => ({
  default: () => <div>Knowledge Panel</div>,
}));

vi.mock("@/components/ImportModal", () => ({
  default: () => null,
}));

vi.mock("@/components/SourcesPanel", () => ({
  default: () => <div>Sources Panel</div>,
}));

vi.mock("@/components/ChatPanel", () => ({
  default: (props: Record<string, unknown>) => {
    chatPanelMock(props);
    return <div>Chat Panel</div>;
  },
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    systemAuthApi: {
      ...actual.systemAuthApi,
      me: vi.fn(),
    },
    sourceBindingApi: {
      ...actual.sourceBindingApi,
      list: vi.fn(),
    },
    chatHistoryApi: {
      ...actual.chatHistoryApi,
      list: vi.fn(),
    },
  };
});

const setMobileViewport = () => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("max-width: 1024px"),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
};

describe("Home mobile shell", () => {
  beforeEach(() => {
    localStorage.clear();
    setMobileViewport();
    vi.mocked(systemAuthApi.me).mockResolvedValue({
      id: 1,
      email: "user@example.com",
      display_name: "User",
    });
    vi.mocked(sourceBindingApi.list).mockResolvedValue([]);
    vi.mocked(chatHistoryApi.list).mockResolvedValue({ items: [] });
    chatPanelMock.mockClear();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("starts with the sidebar collapsed on mobile after login", async () => {
    const { container } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Chat Panel")).toBeInTheDocument();
    });

    expect(container.querySelector(".sidebar-shell")).toHaveClass("closed");
    expect(
      screen.getByRole("button", { name: "展开资料" }),
    ).toBeInTheDocument();
  });

  it("shows the collapsed three-icon toolstrip and keeps the expanded circular collapse button", async () => {
    const user = userEvent.setup();
    const { container } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Chat Panel")).toBeInTheDocument();
    });

    const toolbar = screen.getByRole("toolbar", { name: "工作区快捷入口" });
    expect(toolbar).toHaveClass("workspace-corner-tools");
    expect(screen.getByRole("button", { name: "展开资料" })).toBeVisible();
    expect(screen.getByRole("button", { name: "打开对话历史" })).toBeVisible();
    expect(screen.getByRole("button", { name: "打开笔记" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "展开资料" }));

    expect(container.querySelector(".sidebar-shell")).toHaveClass("open");
    expect(
      screen.queryByRole("toolbar", { name: "工作区快捷入口" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "收起展开页" })).toHaveClass(
      "workspace-sidebar-toggle",
    );
  });

  it("toggles the mobile sidebar from the visible handle", async () => {
    const user = userEvent.setup();
    const { container } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Chat Panel")).toBeInTheDocument();
    });

    expect(container.querySelector(".sidebar-shell")).toHaveClass("closed");

    await user.click(screen.getByRole("button", { name: "展开资料" }));
    expect(container.querySelector(".sidebar-shell")).toHaveClass("open");

    await user.click(screen.getByRole("button", { name: "收起展开页" }));
    expect(container.querySelector(".sidebar-shell")).toHaveClass("closed");
  });

  it("opens conversation history in the expanded page and sends selections to ChatPanel", async () => {
    vi.mocked(chatHistoryApi.list).mockResolvedValue({
      items: [
        {
          id: 42,
          user_id: 1,
          workspace_id: 1,
          knowledge_base_id: 1,
          title: "RAG follow-up",
          scope: null,
          web_search: false,
          web_search_provider: "auto",
          message_count: 2,
          created_at: "2026-06-26T00:00:00Z",
          updated_at: "2026-06-26T01:00:00Z",
        },
      ],
    });
    const user = userEvent.setup();
    const { container } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Chat Panel")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "打开对话历史" }));

    expect(container.querySelector(".sidebar-shell")).toHaveClass("open");
    expect(
      await screen.findByRole("button", { name: "开启新对话" }),
    ).toBeVisible();
    expect(screen.queryByRole("heading", { name: "对话历史" })).toBeNull();
    expect(screen.getByRole("button", { name: "收起展开页" })).toHaveClass(
      "sidebar-history-collapse",
    );
    expect(container.querySelector(".workspace-sidebar-toggle")).toBeNull();
    await user.click(screen.getByRole("button", { name: /RAG follow-up/ }));

    await waitFor(() => {
      const latestProps = chatPanelMock.mock.calls.at(-1)?.[0] as {
        conversationOpenRequest?: { id: number };
      };
      expect(latestProps.conversationOpenRequest?.id).toBe(42);
    });
  });

  it("opens the notes panel from the collapsed toolstrip", async () => {
    const user = userEvent.setup();
    const { container } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Chat Panel")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "打开笔记" }));

    expect(container.querySelector(".sidebar-shell")).toHaveClass("open");
    expect(screen.getByRole("heading", { name: "笔记" })).toBeVisible();
    expect(
      screen.getByPlaceholderText("写下这次学习的要点"),
    ).toBeInTheDocument();
  });

  it("marks the shell with the sidebar state so mobile topbar styles can switch", async () => {
    const { container } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Chat Panel")).toBeInTheDocument();
    });

    expect(container.querySelector(".app-shell")).toHaveClass("sidebar-closed");
    expect(container.querySelector(".app-shell")).not.toHaveClass(
      "sidebar-open",
    );
  });
});
