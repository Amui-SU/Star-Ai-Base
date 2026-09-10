import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const authCss = readFileSync(
  join(process.cwd(), "app/styles/auth.css"),
  "utf8",
);

const desktopRule = (selector: string) => {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return authCss.match(new RegExp(`${escapedSelector}\\s*{([^}]*)}`))?.[1];
};

describe("AuthPage responsive alignment styles", () => {
  it("moves only the desktop brand 16 pixels to the left", () => {
    expect(desktopRule(".auth-page .auth-brand")).toMatch(
      /transform:\s*translateX\(-16px\)/,
    );
  });

  it("moves the desktop form section 24 pixels upward", () => {
    expect(desktopRule(".auth-page .auth-form-section-lowered")).toMatch(
      /transform:\s*translateY\(-24px\)/,
    );
  });

  it("clears both desktop transforms at tablet and mobile widths", () => {
    const responsiveBlock = authCss.match(
      /@media \(max-width: 1024px\) {([\s\S]*?)(?=@media \(max-width: 640px\))/,
    )?.[1];

    expect(responsiveBlock).toMatch(
      /\.auth-page \.auth-brand,\s*\.auth-page \.auth-form-section-lowered\s*{\s*transform:\s*none;/,
    );
  });
});
