import { afterEach, describe, expect, it, vi } from "vitest";
import {
  capacitorHttpRequest,
  importApiForLocation,
  importApiForNativeLocation,
  resetApiTestEnvironment,
} from "./apiTestUtils";

afterEach(resetApiTestEnvironment);

describe("API runtime resolution", () => {
  it("uses the saved native mobile API URL from local connection settings", async () => {
    localStorage.setItem(
      "zhikuyun.localConnection.v1",
      JSON.stringify({ apiBaseUrl: "http://192.168.1.200:8000" }),
    );

    const api = await importApiForLocation({
      protocol: "capacitor:",
      hostname: "localhost",
      origin: "capacitor://localhost",
    });

    expect(api.API_BASE_URL).toBe("http://192.168.1.200:8000");
  });

  it("adds the saved native session token to API requests", async () => {
    localStorage.setItem(
      "zhikuyun.localConnection.v1",
      JSON.stringify({
        apiBaseUrl: "http://192.168.1.200:8000",
        sessionToken: "mobile-token",
      }),
    );
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "healthy" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;

    const api = await importApiForLocation({
      protocol: "capacitor:",
      hostname: "localhost",
      origin: "capacitor://localhost",
    });

    await api.request("/health");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://192.168.1.200:8000/health",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer mobile-token",
        }),
      }),
    );
  });

  it("uses the saved API URL in Capacitor's localhost Android shell", async () => {
    localStorage.setItem(
      "zhikuyun.localConnection.v1",
      JSON.stringify({ apiBaseUrl: "http://192.168.1.200:8000" }),
    );

    const api = await importApiForNativeLocation({
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost",
    });

    expect(api.API_BASE_URL).toBe("http://192.168.1.200:8000");
  });

  it("falls back to CapacitorHttp for native API requests when fetch fails", async () => {
    localStorage.setItem(
      "zhikuyun.localConnection.v1",
      JSON.stringify({ apiBaseUrl: "http://192.168.1.200:8000" }),
    );
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch"));
    capacitorHttpRequest.mockResolvedValue({
      status: 200,
      headers: { "content-type": "application/json" },
      data: {
        user: {
          id: 1,
          email: "phone@example.com",
          display_name: "Phone",
        },
        workspace: { id: 1, name: "Phone", role: "owner" },
        session_token: "mobile-token",
      },
      url: "http://192.168.1.200:8000/system-auth/login",
    });

    const api = await importApiForNativeLocation({
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost",
    });

    await expect(
      api.systemAuthApi.login({
        email: "phone@example.com",
        password: "secret123",
      }),
    ).resolves.toMatchObject({
      user: { email: "phone@example.com" },
    });
    expect(capacitorHttpRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "http://192.168.1.200:8000/system-auth/login",
        method: "POST",
        data: { email: "phone@example.com", password: "secret123" },
      }),
    );
  });
});
