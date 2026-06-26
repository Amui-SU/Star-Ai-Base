import { describe, expect, it } from "vitest";

import {
  displayFolderTitle,
  displayKnowledgeBaseName,
  displayVideoTitle,
  isMissingDisplayText,
} from "@/lib/displayNames";

describe("display name helpers", () => {
  it("normalizes missing and corrupted display text without non-null callers", () => {
    expect(isMissingDisplayText("   ")).toBe(true);
    expect(isMissingDisplayText("????")).toBe(true);
    expect(displayKnowledgeBaseName("  My KB  ")).toBe("My KB");
    expect(displayKnowledgeBaseName("????")).toBe("未命名知识库");
    expect(displayFolderTitle(null)).toBe("未命名收藏夹");
    expect(displayVideoTitle(undefined)).toBe("未命名视频");
  });
});
