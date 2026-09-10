import { describe, expect, it } from "vitest";

import { bilibiliVideoUrl, splitPartBvid } from "./bilibiliVideo";

describe("splitPartBvid", () => {
  it("还原分P存储ID中的真实 bvid 与分P编号", () => {
    expect(splitPartBvid("BV1xx411x7xx_p2")).toEqual({
      bvid: "BV1xx411x7xx",
      page: 2,
    });
    expect(splitPartBvid("BV1xx411x7xx")).toEqual({
      bvid: "BV1xx411x7xx",
      page: null,
    });
    expect(splitPartBvid("LV1234567890ABCDEF12")).toEqual({
      bvid: "LV1234567890ABCDEF12",
      page: null,
    });
  });
});

describe("bilibiliVideoUrl", () => {
  it("分P存储ID自动带 ?p= 参数", () => {
    expect(bilibiliVideoUrl("BV1xx411x7xx")).toBe(
      "https://www.bilibili.com/video/BV1xx411x7xx",
    );
    expect(bilibiliVideoUrl("BV1xx411x7xx_p1")).toBe(
      "https://www.bilibili.com/video/BV1xx411x7xx",
    );
    expect(bilibiliVideoUrl("BV1xx411x7xx_p3")).toBe(
      "https://www.bilibili.com/video/BV1xx411x7xx?p=3",
    );
  });
});
