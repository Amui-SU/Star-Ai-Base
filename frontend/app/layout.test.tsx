import { beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("next/font/google", () => ({
  Inter: () => ({ variable: "font-body" }),
}));

vi.mock("@/components/DevIndicatorGuard", () => ({
  DevIndicatorGuard: () => null,
}));

vi.mock("@/components/LocalConnectionBootstrap", () => ({
  default: () => null,
}));

let RootLayout: typeof import("@/app/layout").default;

beforeAll(async () => {
  RootLayout = (await import("@/app/layout")).default;
});

describe("RootLayout", () => {
  it("suppresses html hydration warnings from browser extensions", () => {
    const element = RootLayout({
      children: <main>content</main>,
    });

    expect(element.type).toBe("html");
    expect(element.props).toMatchObject({
      lang: "zh-CN",
      suppressHydrationWarning: true,
    });
  });
});
