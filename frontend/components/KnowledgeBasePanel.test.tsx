import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import KnowledgeBasePanel from "@/components/KnowledgeBasePanel";
import { knowledgeBaseApi } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    knowledgeBaseApi: {
      ...actual.knowledgeBaseApi,
      list: vi.fn(),
      create: vi.fn(),
      delete: vi.fn(),
    },
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("KnowledgeBasePanel", () => {
  it("uses fallback names for empty or corrupted knowledge bases", async () => {
    const user = userEvent.setup();
    vi.mocked(knowledgeBaseApi.list).mockResolvedValue([
      { id: 1, workspace_id: 1, name: "" },
      { id: 2, workspace_id: 1, name: "   " },
      { id: 3, workspace_id: 1, name: "????" },
    ]);

    render(
      <KnowledgeBasePanel
        activeId={1}
        onSelect={vi.fn()}
        onActiveKnowledgeBase={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("未命名知识库")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /未命名知识库/ }));

    expect(screen.getAllByText("未命名知识库")).toHaveLength(4);
    expect(screen.queryByText("????")).not.toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "删除 未命名知识库" }),
    ).toHaveLength(3);
  });
});
