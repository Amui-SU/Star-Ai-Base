import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AuthPage from "@/components/AuthPage";

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
    hostname: "mobile-preview.example.test",
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("AuthPage third-party login notice", () => {
  it("shows the unavailable notice only after clicking an unsupported provider", async () => {
    const user = userEvent.setup();
    render(<AuthPage onAuthSuccess={vi.fn()} />);

    await waitFor(() => {
      expect(screen.queryByText(thirdPartyNotice)).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole("link", { name: /WeChat/i }));

    expect(screen.getByText(thirdPartyNotice)).toBeInTheDocument();
  });
});