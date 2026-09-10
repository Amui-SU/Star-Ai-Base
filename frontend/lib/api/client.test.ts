import { afterEach, expect, it, vi } from "vitest";
import { request } from "./client";
import { importApi } from "./imports";

afterEach(() => vi.unstubAllGlobals());

it.each([401, 403, 404, 503])(
  "reports task HTTP %s even when the error body never arrives",
  async (status) => {
    let stream!: ReadableStreamDefaultController;
    let cancelled = false;
    const body = new ReadableStream({
      start(controller) {
        stream = controller;
      },
      cancel() {
        cancelled = true;
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(body, { status })),
    );
    let observed: unknown;
    const result = importApi.taskStatus("gone").catch((error) => {
      observed = error;
    });
    try {
      await vi.waitFor(() => expect(observed).toMatchObject({ status }), {
        timeout: 150,
      });
      expect(cancelled).toBe(true);
    } finally {
      if (!cancelled) stream.close();
      await result;
    }
  },
);

it.each([401, 403, 404, 503])(
  "preserves HTTP %s and server message for polling decisions",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: "server detail" }), { status }),
        ),
    );
    await expect(request("/test")).rejects.toMatchObject({
      status,
      message: "server detail",
    });
  },
);

it("passes task cancellation to fetch and keeps AbortError distinguishable", async () => {
  const controller = new AbortController();
  const fetch = vi.fn(
    (_url, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener(
          "abort",
          () => reject(new DOMException("Aborted", "AbortError")),
          { once: true },
        );
      }),
  );
  vi.stubGlobal("fetch", fetch);
  const pending = importApi.taskStatus("task", controller.signal);
  const assertion = expect(pending).rejects.toMatchObject({
    name: "AbortError",
  });
  controller.abort();
  expect(fetch.mock.calls[0][1].signal).toBe(controller.signal);
  await assertion;
});
