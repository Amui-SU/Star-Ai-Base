import { describe, expect, it } from "vitest";

import {
  EMPTY_CHAT_SCOPE,
  normalizeScope,
  scopeEquals,
  scopeSummary,
  toScopePayload,
} from "@/lib/chatScope";

describe("chat scope contracts", () => {
  it("represents an empty selection as the entire knowledge base", () => {
    expect(EMPTY_CHAT_SCOPE).toEqual({ folderIds: [], bvids: [] });
    expect(normalizeScope(EMPTY_CHAT_SCOPE)).toEqual(EMPTY_CHAT_SCOPE);
    expect(scopeSummary(EMPTY_CHAT_SCOPE)).toBe("整个知识库");
    expect(toScopePayload(EMPTY_CHAT_SCOPE)).toEqual({});
  });

  it("deeply freezes the shared empty selection against mutation", () => {
    expect(Object.isFrozen(EMPTY_CHAT_SCOPE)).toBe(true);
    expect(Object.isFrozen(EMPTY_CHAT_SCOPE.folderIds)).toBe(true);
    expect(Object.isFrozen(EMPTY_CHAT_SCOPE.bvids)).toBe(true);

    expect(() => (EMPTY_CHAT_SCOPE.folderIds as number[]).push(1)).toThrow(
      TypeError,
    );
    expect(() => (EMPTY_CHAT_SCOPE.bvids as string[]).push("BV1")).toThrow(
      TypeError,
    );
    expect(EMPTY_CHAT_SCOPE).toEqual({ folderIds: [], bvids: [] });
  });

  it("normalizes duplicate and unordered selections without mutating input", () => {
    const scope = {
      folderIds: [30, 10, 20, 10],
      bvids: ["BV3", "BV1", "BV2", "BV1"],
    };
    const original = {
      folderIds: [...scope.folderIds],
      bvids: [...scope.bvids],
    };

    expect(normalizeScope(scope)).toEqual({
      folderIds: [10, 20, 30],
      bvids: ["BV1", "BV2", "BV3"],
    });
    expect(scope).toEqual(original);
  });

  it("compares selections independent of order and duplicates", () => {
    expect(
      scopeEquals(
        { folderIds: [2, 1, 2], bvids: ["BV2", "BV1"] },
        { folderIds: [1, 2], bvids: ["BV1", "BV2", "BV1"] },
      ),
    ).toBe(true);
    expect(
      scopeEquals(
        { folderIds: [1], bvids: ["BV1"] },
        { folderIds: [1], bvids: ["BV2"] },
      ),
    ).toBe(false);
  });

  it("summarizes folder-only, video-only, and combined selections", () => {
    expect(scopeSummary({ folderIds: [2, 1, 2], bvids: [] })).toBe(
      "2 个收藏夹",
    );
    expect(scopeSummary({ folderIds: [], bvids: ["BV2", "BV1", "BV1"] })).toBe(
      "2 个视频",
    );
    expect(
      scopeSummary({ folderIds: [2, 1, 2], bvids: ["BV2", "BV1", "BV1"] }),
    ).toBe("2 个收藏夹、2 个视频");
  });

  it("creates normalized snake_case payloads for combined selections", () => {
    expect(
      toScopePayload({
        folderIds: [2, 1, 2],
        bvids: ["BV2", "BV1", "BV1"],
      }),
    ).toEqual({
      folder_ids: [1, 2],
      bvids: ["BV1", "BV2"],
    });
  });

  it("omits the unselected class from single-class payloads", () => {
    expect(toScopePayload({ folderIds: [2, 1, 2], bvids: [] })).toEqual({
      folder_ids: [1, 2],
    });
    expect(toScopePayload({ folderIds: [], bvids: ["BV2", "BV1"] })).toEqual({
      bvids: ["BV1", "BV2"],
    });
  });
});
