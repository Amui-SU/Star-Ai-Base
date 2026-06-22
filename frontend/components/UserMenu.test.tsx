import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import UserMenu from "@/components/UserMenu";
import { localConnectionApi, systemAuthApi, type SystemUser } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    localConnectionApi: {
      lanAddress: vi.fn(),
    },
    systemAuthApi: {
      ...actual.systemAuthApi,
      updateDisplayName: vi.fn(),
    },
  };
});

const user: SystemUser = {
  id: 1,
  email: "su1113416467@gmail.com",
  display_name: "苏yiwei",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UserMenu", () => {
  it("shows and copies the detected computer LAN API address", async () => {
    vi.mocked(localConnectionApi.lanAddress).mockResolvedValue({
      host: "192.168.1.200",
      api_url: "http://192.168.1.200:8000",
      frontend_url: "http://192.168.1.200:3000",
      qr_url:
        "http://192.168.1.200:8000/local-connection/mobile-connect.png?api=http%3A%2F%2F192.168.1.200%3A8000",
      qr_image_url:
        "http://192.168.1.200:8000/local-connection/mobile-connect.png?api=http%3A%2F%2F192.168.1.200%3A8000",
      qr_data_url: "data:image/png;base64,fast-inline-qr",
      connect_page_url:
        "http://192.168.1.200:8000/local-connection/mobile-connect?api=http%3A%2F%2F192.168.1.200%3A8000",
    });
    const tester = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<UserMenu user={user} onUserChange={vi.fn()} onLogout={vi.fn()} />);

    await tester.click(screen.getByRole("button", { name: "苏" }));

    expect(await screen.findByText("电脑局域网地址")).toBeInTheDocument();
    expect(screen.getByText("http://192.168.1.200:8000")).toBeInTheDocument();

    await tester.click(
      screen.getByRole("button", { name: /复制电脑局域网地址/ }),
    );

    expect(writeText).toHaveBeenCalledWith("http://192.168.1.200:8000");
    expect(await screen.findByText("手机扫码连接")).toBeInTheDocument();
    expect(screen.getByAltText("手机连接二维码")).toHaveAttribute(
      "src",
      "data:image/png;base64,fast-inline-qr",
    );
    await waitFor(() => {
      expect(screen.getByText("已复制")).toBeInTheDocument();
    });
  });

  it("shows an unavailable LAN address state when detection has no result", async () => {
    vi.mocked(localConnectionApi.lanAddress).mockResolvedValue({
      host: null,
      api_url: null,
      frontend_url: null,
      qr_url: null,
      qr_image_url: null,
      qr_data_url: null,
      connect_page_url: null,
    });
    const tester = userEvent.setup();

    render(<UserMenu user={user} onUserChange={vi.fn()} onLogout={vi.fn()} />);

    await tester.click(screen.getByRole("button", { name: "苏" }));

    expect(await screen.findByText("未检测到局域网地址")).toBeInTheDocument();
  });
});
