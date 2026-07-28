# Video Note ID Reconciliation Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce 3,000-block Markdown ID reconciliation to at most 50 ms without weakening semantic-ID safety.

**Architecture:** Extract ordinary unchanged-block ordering into a pure unique-anchor/LIS helper with O(n log n) time and O(n) memory. Keep semantic section reconciliation in the adapter, then replace repeated full-array gap scans with cursor-based traversal so every candidate is visited a bounded number of times.

**Tech Stack:** TypeScript, Vitest, React/Next.js repository tooling.

---

## File Map

- Create `frontend/components/video-notes/videoNoteSequenceAlignment.ts`: generic unique-fingerprint anchor construction and LIS ordering.
- Create `frontend/components/video-notes/videoNoteSequenceAlignment.test.ts`: algorithm correctness, duplicate safety, and large-input complexity tests.
- Modify `frontend/components/video-notes/videoNoteMarkdownAdapter.ts`: replace the global LCS matrix and repeated gap scans with the new helper and cursor-based gap reconciliation.
- Modify `frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts`: add the end-to-end 3,000-block latency regression and repeated ordinary-block safety coverage.

### Task 1: Lock the performance and duplicate-safety requirements

**Files:**

- Modify: `frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts`

- [ ] **Step 1: Add a failing 3,000-block performance regression**

Add a deterministic test that creates 3,000 uniquely fingerprinted paragraph blocks, removes every 17th block, inserts a small unique paragraph every 31st position, performs one warm-up reconciliation, then measures three reconciliations and asserts that the fastest run is below 50 ms:

```ts
it("reconciles 3000 edited blocks within 50ms", () => {
  const previous = Array.from({ length: 3000 }, (_, index) => ({
    id: `block-${index}`,
    type: "paragraph" as const,
    text: `unique paragraph ${index}`,
  }));
  const edited = previous
    .filter((_, index) => index % 17 !== 0)
    .flatMap((block, index) =>
      index % 31 === 0
        ? [
            {
              id: `new-${index}`,
              type: "paragraph" as const,
              text: `inserted ${index}`,
            },
            block,
          ]
        : [block],
    );
  const markdown = blocksToMarkdown(edited);

  markdownToVideoNoteBlocks(markdown, previous);
  const durations = Array.from({ length: 3 }, () => {
    const startedAt = performance.now();
    markdownToVideoNoteBlocks(markdown, previous);
    return performance.now() - startedAt;
  });

  expect(Math.min(...durations)).toBeLessThan(50);
});
```

- [ ] **Step 2: Add a repeated-fingerprint safety regression**

Add a test where several identical ordinary paragraphs appear on both sides around unique neighbors. Assert that unique neighbors retain IDs and none of the indistinguishable repeated paragraphs inherits an old ID arbitrarily.

```ts
expect(parsed.find((block) => block.text === "left anchor")?.id).toBe("left");
expect(parsed.find((block) => block.text === "right anchor")?.id).toBe("right");
expect(
  parsed
    .filter((block) => block.text === "repeated")
    .every((block) => !block.id.startsWith("old-repeat-")),
).toBe(true);
```

- [ ] **Step 3: Run the tests and verify RED**

Run:

```powershell
cd frontend
npm test -- components/video-notes/videoNoteMarkdownAdapter.test.ts
```

Expected: duplicate-safety behavior remains correct or exposes an existing guess, while the 3,000-block performance test fails above 50 ms against the quadratic matrix.

- [ ] **Step 4: Commit the test-only RED checkpoint**

```powershell
git add frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts
git commit -m "test: cover large video note reconciliation"
```

### Task 2: Implement unique anchors and LIS ordering

**Files:**

- Create: `frontend/components/video-notes/videoNoteSequenceAlignment.ts`
- Create: `frontend/components/video-notes/videoNoteSequenceAlignment.test.ts`

- [ ] **Step 1: Write focused helper tests before the helper exists**

Cover ordered unique matches, insertions/deletions, reordered anchors, and duplicate exclusion:

```ts
expect(alignUniqueFingerprints(["a", "b", "c"], ["a", "x", "b", "c"])).toEqual([
  { previousIndex: 0, parsedIndex: 0 },
  { previousIndex: 1, parsedIndex: 2 },
  { previousIndex: 2, parsedIndex: 3 },
]);
expect(
  alignUniqueFingerprints(
    ["same", "same", "anchor"],
    ["same", "same", "anchor"],
  ),
).toEqual([{ previousIndex: 2, parsedIndex: 2 }]);
expect(alignUniqueFingerprints(["a", "b", "c"], ["c", "b", "a"])).toHaveLength(
  1,
);
```

- [ ] **Step 2: Run the helper test and verify RED**

Run:

```powershell
cd frontend
npm test -- components/video-notes/videoNoteSequenceAlignment.test.ts
```

Expected: FAIL because `videoNoteSequenceAlignment` does not exist.

- [ ] **Step 3: Implement the O(n log n) helper**

Implement frequency/index collection followed by LIS reconstruction. Only fingerprints occurring once on both sides become pairs:

```ts
export interface SequenceMatch {
  previousIndex: number;
  parsedIndex: number;
}

export function alignUniqueFingerprints(
  previous: readonly string[],
  parsed: readonly string[],
): SequenceMatch[] {
  const previousIndexes = collectUniqueIndexes(previous);
  const parsedIndexes = collectUniqueIndexes(parsed);
  const pairs = Array.from(previousIndexes.entries())
    .flatMap(([fingerprint, previousIndex]) => {
      const parsedIndex = parsedIndexes.get(fingerprint);
      return parsedIndex === undefined ? [] : [{ previousIndex, parsedIndex }];
    })
    .sort((left, right) => left.previousIndex - right.previousIndex);
  return longestIncreasingParsedSubsequence(pairs);
}
```

`collectUniqueIndexes` must remove a fingerprint from the unique map as soon as its second occurrence is observed and remember it in a duplicate set so later occurrences cannot re-add it. `longestIncreasingParsedSubsequence` must use binary-search tails plus predecessor indexes to reconstruct matches without sorting or mutating caller arrays.

- [ ] **Step 4: Run helper tests and verify GREEN**

Run:

```powershell
cd frontend
npm test -- components/video-notes/videoNoteSequenceAlignment.test.ts
```

Expected: all helper tests pass.

- [ ] **Step 5: Commit the helper**

```powershell
git add frontend/components/video-notes/videoNoteSequenceAlignment.ts frontend/components/video-notes/videoNoteSequenceAlignment.test.ts
git commit -m "perf: add near-linear video note alignment"
```

### Task 3: Replace global LCS and repeated gap scans

**Files:**

- Modify: `frontend/components/video-notes/videoNoteMarkdownAdapter.ts`
- Test: `frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts`

- [ ] **Step 1: Replace the matrix with unique ordered anchors**

Import `alignUniqueFingerprints`. Build candidate fingerprint arrays once, call the helper, and translate returned candidate indexes back to actual block indexes before calling `assign`:

```ts
for (const match of alignUniqueFingerprints(
  previousCandidates.map((candidate) => candidate.fingerprint),
  parsedCandidates.map((candidate) => candidate.fingerprint),
)) {
  const previousCandidate = previousCandidates[match.previousIndex];
  const parsedCandidate = parsedCandidates[match.parsedIndex];
  assign(parsedCandidate.index, [previousBlocks[previousCandidate.index].id]);
}
```

Delete the complete two-dimensional `lcs` allocation and backtracking loop.

- [ ] **Step 2: Make gap reconciliation linear**

Precompute eligible parsed and previous candidates once. Walk sorted monotonic anchors with two cursors. For each gap, compare only the candidate slices between the current and next anchor; do not call `.map().filter()` over all blocks inside the anchor loop.

```ts
let parsedCursor = 0;
let previousCursor = 0;
for (const anchor of orderedAnchorsWithSentinel) {
  const parsedGapStart = parsedCursor;
  while (
    parsedCursor < eligibleParsed.length &&
    eligibleParsed[parsedCursor].index < anchor.parsedIndex
  )
    parsedCursor += 1;
  const previousGapStart = previousCursor;
  while (
    previousCursor < eligiblePrevious.length &&
    eligiblePrevious[previousCursor].index < anchor.previousIndex
  )
    previousCursor += 1;
  reconcileCompatibleEqualLengthGap(
    eligibleParsed.slice(parsedGapStart, parsedCursor),
    eligiblePrevious.slice(previousGapStart, previousCursor),
  );
}
```

The gap helper must assign only equal-length, positionally kind-compatible gaps. Ambiguous semantic candidates and already assigned/used candidates remain excluded.

- [ ] **Step 3: Run focused tests and verify GREEN**

Run:

```powershell
cd frontend
npm test -- components/video-notes/videoNoteSequenceAlignment.test.ts components/video-notes/videoNoteMarkdownAdapter.test.ts components/video-notes/VideoNoteWorkspace.ai.test.tsx
```

Expected: all tests pass and the measured 3,000-block minimum is below 50 ms.

- [ ] **Step 4: Run all video-note tests and static checks**

Run:

```powershell
cd frontend
npm test -- components/video-notes
npx prettier --check components/video-notes/videoNoteSequenceAlignment.ts components/video-notes/videoNoteSequenceAlignment.test.ts components/video-notes/videoNoteMarkdownAdapter.ts components/video-notes/videoNoteMarkdownAdapter.test.ts
npx eslint components/video-notes/videoNoteSequenceAlignment.ts components/video-notes/videoNoteSequenceAlignment.test.ts components/video-notes/videoNoteMarkdownAdapter.ts components/video-notes/videoNoteMarkdownAdapter.test.ts
npm run build
```

Expected: all video-note tests, formatting, lint, TypeScript build, and production build pass.

- [ ] **Step 5: Commit adapter integration**

```powershell
git add frontend/components/video-notes/videoNoteMarkdownAdapter.ts frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts
git commit -m "perf: remove quadratic video note reconciliation"
```

### Task 4: Verify and publish

**Files:**

- Verify only; no planned production changes.

- [ ] **Step 1: Run complete repository verification**

Run:

```powershell
& .\scripts\verify-before-commit.ps1 -Format
& .\scripts\verify-before-commit.ps1
```

Expected: backend tests, frontend tests, lint, formatting, and production build all pass.

- [ ] **Step 2: Confirm commit and worktree hygiene**

Run:

```powershell
git status --short
git diff --check origin/agent/video-note-ui-polish...HEAD
git log --oneline origin/agent/video-note-ui-polish..HEAD
```

Expected: clean worktree, no whitespace errors, and only the design/plan/performance commits are ahead of the remote branch.

- [ ] **Step 3: Push the existing feature branch**

```powershell
git push origin agent/video-note-ui-polish
```

Expected: `origin/agent/video-note-ui-polish` advances to the local HEAD without force-push.
