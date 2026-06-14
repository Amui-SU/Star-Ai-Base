import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Home from "@/app/page";
import { sourceBindingApi, systemAuthApi } from "@/lib/api";

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
  default: () => <div>Chat Panel</div>,
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
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
  });

  it("toggles the mobile sidebar from the visible handle", async () => {
    const user = userEvent.setup();
    const { container } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Chat Panel")).toBeInTheDocument();
    });

    expect(container.querySelector(".sidebar-shell")).toHaveClass("closed");

    await user.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(container.querySelector(".sidebar-shell")).toHaveClass("open");

    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(container.querySelector(".sidebar-shell")).toHaveClass("closed");
  });

  it("marks the shell with the sidebar state so mobile topbar styles can switch", async () => {
    const { container } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Chat Panel")).toBeInTheDocument();
    });

    expect(container.querySelector(".app-shell")).toHaveClass("sidebar-closed");
    expect(container.querySelector(".app-shell")).not.toHaveClass("sidebar-open");
  });
});
