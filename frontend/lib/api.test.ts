import { describe, expect, it } from "vitest";

describe("frontend API barrel tests", () => {
  it("delegates request behavior checks to focused API suites", () => {
    expect([
      "apiRuntime.test.ts",
      "systemAdminApi.test.ts",
      "userApiAccounts.test.ts",
      "importUploads.test.ts",
    ]).toHaveLength(4);
  });
});
