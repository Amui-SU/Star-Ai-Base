import { afterEach, describe, expect, it, vi } from "vitest";

const request = vi.fn();

vi.mock("@capacitor/core", () => ({
  Capacitor: {
    isNativePlatform: () => true,
  },
  CapacitorHttp: {
    request,
  },
}));

const originalFetch = globalThis.fetch;

afterEach(() => {
  vi.clearAllMocks();
  globalThis.fetch = originalFetch;
});

describe("requestWithNativeFallback", () => {
  it("uses CapacitorHttp when native fetch cannot reach a LAN backend", async () => {
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch"));
    request.mockResolvedValue({
      status: 200,
      headers: { "content-type": "application/json" },
      data: { status: "healthy" },
      url: "http://192.168.1.200:8000/health",
    });

    const { requestWithNativeFallback } = await import("./nativeHttp");
    const response = await requestWithNativeFallback(
      "http://192.168.1.200:8000/health",
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      },
    );

    await expect(response.json()).resolves.toEqual({ status: "healthy" });
    expect(request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "http://192.168.1.200:8000/health",
        method: "GET",
        headers: expect.objectContaining({
          "content-type": "application/json",
        }),
      }),
    );
  });

  it("passes JSON request bodies to CapacitorHttp as objects", async () => {
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch"));
    request.mockResolvedValue({
      status: 200,
      headers: { "content-type": "application/json" },
      data: { ok: true },
      url: "http://192.168.1.200:8000/system-auth/login",
    });

    const { requestWithNativeFallback } = await import("./nativeHttp");
    await requestWithNativeFallback(
      "http://192.168.1.200:8000/system-auth/login",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "a@example.com", password: "secret" }),
      },
    );

    expect(request).toHaveBeenCalledWith(
      expect.objectContaining({
        data: { email: "a@example.com", password: "secret" },
      }),
    );
  });
});
