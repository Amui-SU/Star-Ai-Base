import { vi } from "vitest";

const originalEnv = process.env.NEXT_PUBLIC_API_URL;
const originalLocation = window.location;
const originalFetch = globalThis.fetch;

export const capacitorHttpRequest = vi.fn();

export async function importApiForLocation(location: Partial<Location>) {
  vi.resetModules();
  delete process.env.NEXT_PUBLIC_API_URL;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      ...originalLocation,
      ...location,
    },
  });
  return import("@/lib/api");
}

export async function importApiForNativeLocation(location: Partial<Location>) {
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
  return import("@/lib/api");
}

export function resetApiTestEnvironment() {
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
}
