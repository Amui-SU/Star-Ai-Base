import { afterEach, describe, expect, it, vi } from "vitest";
import { importApiForLocation, resetApiTestEnvironment } from "./apiTestUtils";

afterEach(resetApiTestEnvironment);

describe("user API accounts", () => {
  it("wraps user API account requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 1,
            provider: "deepseek",
            provider_label: "DeepSeek",
            display_name: "DeepSeek",
            base_url: "https://api.deepseek.com/v1",
            model: "deepseek-chat",
            thinking_config: {},
            enabled: true,
            is_default: true,
            configured: true,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 1,
            provider: "deepseek",
            provider_label: "DeepSeek",
            display_name: "My DeepSeek",
            base_url: "https://api.deepseek.com/v1",
            model: "deepseek-chat",
            thinking_config: {},
            enabled: true,
            is_default: true,
            configured: true,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 1,
            provider: "deepseek",
            provider_label: "DeepSeek",
            display_name: "My DeepSeek",
            base_url: "https://api.deepseek.com/v1",
            model: "deepseek-chat",
            thinking_config: {},
            enabled: true,
            is_default: true,
            configured: true,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "success",
            message: "连接成功",
            http_status: 200,
            section: "connection",
            latency_ms: 42,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    globalThis.fetch = fetchMock;

    const api = await importApiForLocation({
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost:3000",
    });

    await expect(api.apiAccountApi.list()).resolves.toEqual([]);
    await expect(
      api.apiAccountApi.create({
        provider: "deepseek",
        api_key: "sk-user-secret",
        model: "deepseek-chat",
      }),
    ).resolves.toMatchObject({ provider: "deepseek" });
    await expect(
      api.apiAccountApi.update(1, { display_name: "My DeepSeek" }),
    ).resolves.toMatchObject({ display_name: "My DeepSeek" });
    await expect(api.apiAccountApi.setDefault(1)).resolves.toMatchObject({
      is_default: true,
    });
    await expect(
      api.apiAccountApi.validateDraft({
        provider: "claude",
        api_key: "sk-current-draft",
        protocol: "anthropic_messages",
        auth_scheme: "x_api_key",
        advanced_config: { version: 1 },
      }),
    ).resolves.toMatchObject({ status: "success", latency_ms: 42 });
    await expect(api.apiAccountApi.remove(1)).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api-accounts",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api-accounts",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          provider: "deepseek",
          api_key: "sk-user-secret",
          model: "deepseek-chat",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api-accounts/1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ display_name: "My DeepSeek" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://localhost:8000/api-accounts/1/set-default",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://localhost:8000/api-accounts/validate-draft",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("sk-current-draft"),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "http://localhost:8000/api-accounts/1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
