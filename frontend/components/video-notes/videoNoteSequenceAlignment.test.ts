import { describe, expect, it } from "vitest";

import { alignUniqueFingerprints } from "./videoNoteSequenceAlignment";

describe("alignUniqueFingerprints", () => {
  it("matches ordered fingerprints that are unique on both sides", () => {
    const previous = ["a", "b", "c"] as const;
    const parsed = ["a", "b", "c"] as const;

    expect(alignUniqueFingerprints(previous, parsed)).toEqual([
      { previousIndex: 0, parsedIndex: 0 },
      { previousIndex: 1, parsedIndex: 1 },
      { previousIndex: 2, parsedIndex: 2 },
    ]);
    expect(previous).toEqual(["a", "b", "c"]);
    expect(parsed).toEqual(["a", "b", "c"]);
  });

  it("keeps ordered anchors around insertions and deletions", () => {
    expect(
      alignUniqueFingerprints(
        ["removed", "a", "b", "c"],
        ["a", "inserted", "b", "c"],
      ),
    ).toEqual([
      { previousIndex: 1, parsedIndex: 0 },
      { previousIndex: 2, parsedIndex: 2 },
      { previousIndex: 3, parsedIndex: 3 },
    ]);
  });

  it("does not match a fingerprint repeated twice on either side", () => {
    expect(
      alignUniqueFingerprints(
        ["same", "same", "anchor"],
        ["same", "same", "anchor"],
      ),
    ).toEqual([{ previousIndex: 2, parsedIndex: 2 }]);
  });

  it("returns one order-preserving match for a reversed sequence", () => {
    const matches = alignUniqueFingerprints(["a", "b", "c"], ["c", "b", "a"]);

    expect(matches).toHaveLength(1);
    expect(
      matches.every((match, index) => {
        const prior = matches[index - 1];
        return (
          prior === undefined ||
          (prior.previousIndex < match.previousIndex &&
            prior.parsedIndex < match.parsedIndex)
        );
      }),
    ).toBe(true);
  });

  it("returns no matches when either input is empty", () => {
    expect(alignUniqueFingerprints([], ["a"])).toEqual([]);
    expect(alignUniqueFingerprints(["a"], [])).toEqual([]);
    expect(alignUniqueFingerprints([], [])).toEqual([]);
  });

  it("never restores a fingerprint to the unique set after its third occurrence", () => {
    expect(
      alignUniqueFingerprints(
        ["repeat", "repeat", "repeat", "anchor"],
        ["repeat", "anchor"],
      ),
    ).toEqual([{ previousIndex: 3, parsedIndex: 1 }]);

    expect(
      alignUniqueFingerprints(
        ["repeat", "anchor"],
        ["repeat", "repeat", "repeat", "anchor"],
      ),
    ).toEqual([{ previousIndex: 1, parsedIndex: 3 }]);
  });

  it("aligns ten thousand unique fingerprints with insertions and deletions", () => {
    const previous = Array.from(
      { length: 10_000 },
      (_, index) => `item-${index}`,
    );
    const parsed = ["inserted", ...previous.slice(1, 9_999)];

    const startedAt = performance.now();
    const matches = alignUniqueFingerprints(previous, parsed);
    const elapsedMs = performance.now() - startedAt;

    expect(matches).toHaveLength(9_998);
    expect(matches[0]).toEqual({ previousIndex: 1, parsedIndex: 1 });
    expect(matches.at(-1)).toEqual({
      previousIndex: 9_998,
      parsedIndex: 9_998,
    });
    expect(elapsedMs).toBeLessThan(250);
  });
});
