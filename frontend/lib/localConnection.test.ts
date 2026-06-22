import { afterEach, describe, expect, it, vi } from "vitest";

const originalLocation = window.location;

async function importLocalConnectionForLocation(
  location: Partial<Location>,
  { nativePlatform = false }: { nativePlatform?: boolean } = {},
) {
  vi.resetModules();
  vi.doMock("@capacitor/core", () => ({
    Capacitor: {
      isNativePlatform: () => nativePlatform,
    },
  }));
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      ...originalLocation,
      ...location,
    },
  });
  return import("./localConnection");
}

afterEach(() => {
  vi.resetModules();
  vi.doUnmock("@capacitor/core");
  localStorage.clear();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

describe("local connection settings", () => {
  it("normalizes a LAN host into the backend API URL", async () => {
    const { normalizeLocalApiBaseUrl } = await importLocalConnectionForLocation(
      {
        protocol: "capacitor:",
        hostname: "localhost",
      },
    );

    expect(normalizeLocalApiBaseUrl("192.168.1.200")).toBe(
      "http://192.168.1.200:8000",
    );
    expect(normalizeLocalApiBaseUrl("http://192.168.1.200:3000")).toBe(
      "http://192.168.1.200:8000",
    );
  });

  it("persists the normalized API URL for the native shell", async () => {
    const { getSavedLocalConnection, hasLocalConnection, saveLocalConnection } =
      await importLocalConnectionForLocation({
        protocol: "capacitor:",
        hostname: "localhost",
      });

    saveLocalConnection("192.168.1.200");

    expect(hasLocalConnection()).toBe(true);
    expect(getSavedLocalConnection()?.apiBaseUrl).toBe(
      "http://192.168.1.200:8000",
    );
  });

  it("detects Capacitor's localhost Android shell as native", async () => {
    const { isNativeShell } = await importLocalConnectionForLocation(
      {
        protocol: "http:",
        hostname: "localhost",
        origin: "http://localhost",
      },
      { nativePlatform: true },
    );

    expect(isNativeShell()).toBe(true);
  });

  it("extracts the API URL from a connect deep link", async () => {
    const { parseLocalConnectionUrl } = await importLocalConnectionForLocation({
      protocol: "capacitor:",
      hostname: "localhost",
    });

    expect(
      parseLocalConnectionUrl(
        "zhikuyun://connect?api=http%3A%2F%2F192.168.1.200%3A8000",
      ),
    ).toBe("http://192.168.1.200:8000");
  });

  it("extracts the API URL from the QR image URL", async () => {
    const { parseLocalConnectionUrl } = await importLocalConnectionForLocation({
      protocol: "capacitor:",
      hostname: "localhost",
    });

    expect(
      parseLocalConnectionUrl(
        "http://192.168.1.200:8000/local-connection/mobile-connect.png?api=http%3A%2F%2F192.168.1.200%3A8000",
      ),
    ).toBe("http://192.168.1.200:8000");
  });

  it("saves the API URL from launch query parameters", async () => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        ...originalLocation,
        protocol: "capacitor:",
        hostname: "localhost",
        search: "?api=http%3A%2F%2F192.168.1.200%3A8000",
      },
    });
    vi.resetModules();
    const { applyLaunchConnectionFromLocation, getSavedLocalConnection } =
      await import("./localConnection");

    expect(applyLaunchConnectionFromLocation()).toBe(true);
    expect(getSavedLocalConnection()?.apiBaseUrl).toBe(
      "http://192.168.1.200:8000",
    );
  });
});
