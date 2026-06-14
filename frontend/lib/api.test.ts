import { afterEach, describe, expect, it, vi } from "vitest";

const originalEnv = process.env.NEXT_PUBLIC_API_URL;
const originalLocation = window.location;

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

afterEach(() => {
  vi.resetModules();
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
  it("does not build native mobile API URLs from the Capacitor protocol", async () => {
    const api = await importApiForLocation({
      protocol: "capacitor:",
      hostname: "localhost",
      origin: "capacitor://localhost",
    });

    expect(api.API_BASE_URL).toBe("http://localhost:8000");
  });
});
