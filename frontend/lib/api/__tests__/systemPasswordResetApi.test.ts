import { afterEach, describe, expect, it, vi } from "vitest";

import { importApiForLocation, resetApiTestEnvironment } from "./apiTestUtils";

afterEach(resetApiTestEnvironment);

describe("system password reset API", () => {
  it("wraps password reset send and confirm requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ message: "code sent", code: "123456" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ message: "password reset" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    globalThis.fetch = fetchMock;

    const api = await importApiForLocation({
      protocol: "http:",
      hostname: "localhost",
      origin: "http://localhost:3000",
    });

    await api.systemAuthApi.sendPasswordResetCode("member@example.com");
    await api.systemAuthApi.confirmPasswordReset({
      email: "member@example.com",
      code: "123456",
      new_password: "new secure password",
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/system-auth/password-reset/send-code",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "member@example.com" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/system-auth/password-reset/confirm",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "member@example.com",
          code: "123456",
          new_password: "new secure password",
        }),
      }),
    );
  });
});
