import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AuthPage from "@/components/AuthPage";

vi.mock("@/components/LocalConnectionSettings", () => ({
  default: () => (
    <button type="button" className="local-connection-trigger">
      连接设置
    </button>
  ),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    systemAuthApi: {
      ...actual.systemAuthApi,
      getOAuthLoginUrl: vi.fn((provider: string) => `/oauth/${provider}`),
    },
  };
});

const thirdPartyNotice = /WeChat and QQ login are not configured yet/i;

beforeEach(() => {
  vi.stubGlobal("location", {
    ...window.location,
    protocol: "http:",
    hostname: "mobile-preview.example.test",
    origin: "http://mobile-preview.example.test",
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("AuthPage third-party login notice", () => {
  it("enables Google login on a public HTTPS origin", () => {
    vi.stubGlobal("location", {
      ...window.location,
      protocol: "https:",
      hostname: "zhiku-cloud.cn",
      origin: "https://zhiku-cloud.cn",
    });

    render(<AuthPage onAuthSuccess={vi.fn()} />);

    const googleLink = screen.getByRole("link", { name: /Google/i });
    expect(googleLink).toHaveAttribute("href", "/oauth/google");
    expect(googleLink).toHaveAttribute("aria-disabled", "false");
  });

  it("keeps Google login disabled on local preview origins", async () => {
    vi.stubGlobal("location", {
      ...window.location,
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost",
    });
    const user = userEvent.setup();
    render(<AuthPage onAuthSuccess={vi.fn()} />);

    const googleLink = screen.getByRole("link", { name: /Google/i });
    expect(googleLink).toHaveAttribute("href", "#");

    await user.click(googleLink);

    expect(
      screen.getByText(/Google login requires an HTTPS public callback/i),
    ).toBeInTheDocument();
  });

  it("shows the unavailable notice only after clicking an unsupported provider", async () => {
    const user = userEvent.setup();
    render(<AuthPage onAuthSuccess={vi.fn()} />);

    await waitFor(() => {
      expect(screen.queryByText(thirdPartyNotice)).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole("link", { name: /WeChat/i }));

    expect(screen.getByText(thirdPartyNotice)).toBeInTheDocument();
  });

  it("renders compact social login buttons in a dedicated centered group", () => {
    const { container } = render(<AuthPage onAuthSuccess={vi.fn()} />);

    const oauthGroup = container.querySelector(".auth-oauth-grid");

    expect(oauthGroup).toBeInTheDocument();
    expect(oauthGroup).toContainElement(
      screen.getByRole("link", { name: /Google/i }),
    );
    expect(oauthGroup).toContainElement(
      screen.getByRole("link", { name: /WeChat/i }),
    );
    expect(oauthGroup).toContainElement(
      screen.getByRole("link", { name: /QQ/i }),
    );
  });

  it("keeps connection settings in a separate header action area", () => {
    const { container } = render(<AuthPage onAuthSuccess={vi.fn()} />);

    const actionArea = container.querySelector(".auth-header-actions");

    expect(actionArea).toBeInTheDocument();
    expect(actionArea).toContainElement(
      screen.getByRole("button", { name: "连接设置" }),
    );
  });

  it("marks the login module as movable for mobile vertical tuning", () => {
    const { container } = render(<AuthPage onAuthSuccess={vi.fn()} />);

    expect(container.querySelector(".auth-form-section")).toHaveClass(
      "auth-form-section-lowered",
    );
  });

  it("groups the primary email input and continue button for narrower mobile sizing", () => {
    const { container } = render(<AuthPage onAuthSuccess={vi.fn()} />);

    const primaryControls = container.querySelector(".auth-primary-controls");

    expect(primaryControls).toBeInTheDocument();
    expect(primaryControls).toContainElement(
      screen.getByPlaceholderText("输入邮箱地址"),
    );
    expect(primaryControls).toContainElement(
      screen.getByRole("button", { name: "继续" }),
    );
  });

  it("keeps the no-account hint outside the auth card for lower mobile placement", () => {
    const { container } = render(<AuthPage onAuthSuccess={vi.fn()} />);
    const section = container.querySelector(".auth-form-section");
    const accountHint = screen.getByText("没有账号？继续后即可创建");

    expect(accountHint).toHaveClass("auth-account-hint");
    expect(container.querySelector(".auth-card")).not.toContainElement(
      accountHint,
    );
    expect(accountHint.parentElement).toBe(section);
  });

  it("forces the login screen back to dark theme even after leaving light mode", () => {
    document.documentElement.classList.add("light");

    render(<AuthPage onAuthSuccess={vi.fn()} />);

    expect(document.documentElement).toHaveClass("auth-page-active");
    expect(document.documentElement).not.toHaveClass("light");
  });
});
