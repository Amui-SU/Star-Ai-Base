import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(
  resolve(process.cwd(), "app", "globals.css"),
  "utf8",
);

describe("mobile chat message layout", () => {
  it("keeps edited user messages right-aligned and insets assistant replies", () => {
    expect(stylesheet).toMatch(
      /\.message\.user \.message-bubble\.editing\s*\{[^}]*align-self:\s*flex-end;[^}]*width:\s*min\(88%, 600px\);/s,
    );
    expect(stylesheet).toMatch(
      /\.message\.assistant \.message-main\s*\{[^}]*padding-inline:\s*clamp\(12px, 4vw, 24px\);/s,
    );
    expect(stylesheet).toMatch(
      /\.message\.assistant \.markdown\s*\{[^}]*text-align:\s*left;/s,
    );
  });
});
