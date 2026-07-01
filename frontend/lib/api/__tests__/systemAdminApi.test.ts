import { afterEach, describe, expect, it, vi } from "vitest";
import { importApiForLocation, resetApiTestEnvironment } from "./apiTestUtils";

afterEach(resetApiTestEnvironment);

describe("system admin API", () => {
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
});
