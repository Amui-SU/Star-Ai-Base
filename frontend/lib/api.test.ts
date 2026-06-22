import { afterEach, describe, expect, it, vi } from "vitest";

const originalEnv = process.env.NEXT_PUBLIC_API_URL;
const originalLocation = window.location;
const originalFetch = globalThis.fetch;
const capacitorHttpRequest = vi.fn();

async function importApiForLocation(location: Partial<Location>) {
  vi.resetModules();
  delete process.env.NEXT_PUBLIC_API_URL;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      ...originalLocation,
      ...location,
    },
  });
  return import("./api");
}

async function importApiForNativeLocation(location: Partial<Location>) {
  vi.resetModules();
  vi.doMock("@capacitor/core", () => ({
    Capacitor: {
      isNativePlatform: () => true,
    },
    CapacitorHttp: {
      request: capacitorHttpRequest,
    },
  }));
  delete process.env.NEXT_PUBLIC_API_URL;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      ...originalLocation,
      ...location,
    },
  });
  return import("./api");
}

afterEach(() => {
  vi.resetModules();
  vi.doUnmock("@capacitor/core");
  capacitorHttpRequest.mockReset();
  localStorage.clear();
  globalThis.fetch = originalFetch;
  if (originalEnv === undefined) {
    delete process.env.NEXT_PUBLIC_API_URL;
  } else {
    process.env.NEXT_PUBLIC_API_URL = originalEnv;
  }
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

describe("API base URL resolution", () => {
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

  it("wraps admin user management requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            users: [
              {
                id: 1,
                email: "admin@example.com",
                display_name: "Admin",
                status: "active",
                is_admin: true,
                created_at: "2026-06-22T00:00:00Z",
                updated_at: "2026-06-22T00:00:00Z",
              },
            ],
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
            id: 2,
            email: "member@example.com",
            display_name: "Member",
            status: "inactive",
            is_admin: false,
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
            user: {
              id: 2,
              email: "member@example.com",
              display_name: "Member",
              status: "active",
              is_admin: false,
            },
            temporary_password: "temporary-password",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    globalThis.fetch = fetchMock;

    const api = await importApiForLocation({
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost:3000",
    });

    await expect(api.systemAuthApi.adminListUsers()).resolves.toHaveLength(1);
    await expect(
      api.systemAuthApi.adminUpdateUserStatus(2, "inactive"),
    ).resolves.toMatchObject({
      id: 2,
      status: "inactive",
    });
    await expect(
      api.systemAuthApi.adminResetUserPassword(2),
    ).resolves.toMatchObject({
      temporary_password: "temporary-password",
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/system-auth/admin/users",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/system-auth/admin/users/2/status",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ status: "inactive" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/system-auth/admin/users/2/reset-password",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("uploads local videos with FormData and no JSON content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          status: "pending",
          source_type: "local_video",
          message: "已创建本地视频导入任务",
          task_id: "task-local",
          bvid: "LV123",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const api = await importApiForLocation({
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost:3000",
    });
    const file = new File(["video"], "demo.mp4", { type: "video/mp4" });

    await expect(
      api.importApi.importLocalVideo({
        file,
        knowledge_base_id: 7,
        title: "demo.mp4",
      }),
    ).resolves.toMatchObject({
      source_type: "local_video",
      task_id: "task-local",
    });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8000/imports/local-video",
    );
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers).not.toHaveProperty("Content-Type");
  });
});
