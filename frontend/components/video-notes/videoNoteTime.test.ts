import { describe, expect, it } from "vitest";

import { formatVideoNoteTime } from "./videoNoteTime";

describe("formatVideoNoteTime", () => {
  it.each([
    [204, "03:24"],
    [3723, "01:02:03"],
    [360000, "100:00:00"],
    [-1, "00:00"],
    [Number.NaN, "00:00"],
    [Number.POSITIVE_INFINITY, "00:00"],
    ["204", "00:00"],
    [true, "00:00"],
  ])("formats %p as %s", (value, expected) => {
    expect(formatVideoNoteTime(value)).toBe(expected);
  });
});
