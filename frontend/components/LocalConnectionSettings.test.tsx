import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import LocalConnectionSettings from "@/components/LocalConnectionSettings";
import { scanLocalConnectionQrCode } from "@/lib/localConnectionScanner";

vi.mock("@/lib/localConnectionScanner", () => ({
  scanLocalConnectionQrCode: vi.fn(),
}));

const originalLocation = window.location;
const originalFetch = globalThis.fetch;

function setNativeLocation() {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      ...originalLocation,
      protocol: "capacitor:",
      hostname: "localhost",
      origin: "capacitor://localhost",
    },
  });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
  globalThis.fetch = originalFetch;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

describe("LocalConnectionSettings", () => {
  it("stores a tested local backend address in the native shell", async () => {
    setNativeLocation();
    const user = userEvent.setup();
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "healthy" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<LocalConnectionSettings />);

    await user.click(screen.getByRole("button", { name: "连接设置" }));
    expect(
      screen
        .getByLabelText("电脑端地址")
        .closest(".local-connection-modal-backdrop")?.parentElement,
    ).toBe(document.body);
    await user.clear(screen.getByLabelText("电脑端地址"));
    await user.type(screen.getByLabelText("电脑端地址"), "192.168.1.200");
    await user.click(screen.getByRole("button", { name: "测试并保存" }));

    expect(await screen.findByText("连接可用，已保存")).toBeInTheDocument();
    expect(localStorage.getItem("zhikuyun.localConnection.v1")).toContain(
      "http://192.168.1.200:8000",
    );
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://192.168.1.200:8000/health",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("closes the settings card and leaves a clear success notice after saving", async () => {
    setNativeLocation();
    const user = userEvent.setup();
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "healthy" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<LocalConnectionSettings />);

    await user.click(screen.getByRole("button", { name: "连接设置" }));
    await user.clear(screen.getByLabelText("电脑端地址"));
    await user.type(screen.getByLabelText("电脑端地址"), "192.168.1.200");
    await user.click(screen.getByRole("button", { name: "测试并保存" }));

    expect(await screen.findByText("连接可用，已保存")).toHaveClass(
      "local-connection-saved-notice",
    );
    expect(screen.queryByLabelText("电脑端地址")).not.toBeInTheDocument();
  });

  it("scans a QR code and saves the decoded backend address", async () => {
    setNativeLocation();
    const user = userEvent.setup();
    vi.mocked(scanLocalConnectionQrCode).mockResolvedValue(
      "http://192.168.1.200:8000",
    );
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "healthy" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<LocalConnectionSettings />);

    await user.click(screen.getByRole("button", { name: "连接设置" }));
    await user.click(screen.getByRole("button", { name: "扫码" }));

    expect(scanLocalConnectionQrCode).toHaveBeenCalledOnce();
    expect(await screen.findByText("连接可用，已保存")).toHaveClass(
      "local-connection-saved-notice",
    );
    expect(localStorage.getItem("zhikuyun.localConnection.v1")).toContain(
      "http://192.168.1.200:8000",
    );
  });

  it("shows fetch failures as a red error message", async () => {
    setNativeLocation();
    const user = userEvent.setup();
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch"));

    render(<LocalConnectionSettings />);

    await user.click(screen.getByRole("button", { name: "连接设置" }));
    await user.clear(screen.getByLabelText("电脑端地址"));
    await user.type(screen.getByLabelText("电脑端地址"), "192.168.1.200");
    await user.click(screen.getByRole("button", { name: "测试并保存" }));

    expect(await screen.findByText("Failed to fetch")).toHaveClass(
      "local-connection-message-error",
    );
  });
});
