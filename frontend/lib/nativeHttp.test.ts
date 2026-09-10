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
  it("does not start native fallback after fetch is cancelled", async () => {
    const controller = new AbortController();
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new DOMException("Aborted", "AbortError"));
    controller.abort();
    const { requestWithNativeFallback } = await import("./nativeHttp");
    await expect(
      requestWithNativeFallback("http://localhost/test", {
        signal: controller.signal,
      }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(request).not.toHaveBeenCalled();
  });
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

  it("passes FormData uploads to CapacitorHttp as native form data", async () => {
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch"));
    request.mockResolvedValue({
      status: 200,
      headers: { "content-type": "application/json" },
      data: { ok: true },
      url: "http://192.168.1.200:8000/imports/local-video",
    });

    const { requestWithNativeFallback } = await import("./nativeHttp");
    const formData = new FormData();
    formData.set(
      "file",
      new File(["video"], "demo.mp4", { type: "video/mp4" }),
    );
    formData.set("knowledge_base_id", "7");

    const response = await requestWithNativeFallback(
      "http://192.168.1.200:8000/imports/local-video",
      {
        method: "POST",
        body: formData,
      },
    );

    await expect(response.json()).resolves.toEqual({ ok: true });
    expect(request).toHaveBeenCalledWith(
      expect.objectContaining({
        dataType: "formData",
        data: [
          expect.objectContaining({
            key: "file",
            type: "base64File",
            contentType: "video/mp4",
            fileName: "demo.mp4",
            value: "dmlkZW8=",
          }),
          { key: "knowledge_base_id", value: "7", type: "string" },
        ],
      }),
    );
  });
});
