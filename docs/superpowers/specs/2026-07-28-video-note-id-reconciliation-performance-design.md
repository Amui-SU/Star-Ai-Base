# Video Note ID Reconciliation Performance Design

## Goal

Reduce `markdownToVideoNoteBlocks` ID reconciliation latency for a 3,000-block note to at most 50 ms on the repository test environment, while preserving the existing safety rule: when duplicate semantic sections cannot be distinguished reliably, do not assign a stable AI target ID.

## Current Problem

`reconcileBlockIds` builds a complete `(previous + 1) × (parsed + 1)` LCS matrix. Its time and memory are both O(n²). A synthetic 3,000-block round trip takes roughly 363 ms and allocates millions of matrix cells during editor input.

Semantic section handling is already separate from ordinary unchanged-block matching. The optimization therefore replaces only the global LCS phase and retains the existing semantic-section ambiguity rules.

## Selected Algorithm

### 1. Preserve semantic assignments first

Keep the current semantic heading/content reconciliation, including duplicate-section disambiguation and the conservative no-guess fallback. Assigned or ambiguous semantic candidates are excluded from ordinary matching.

### 2. Build unique fingerprint anchors

Build frequency and index maps for the remaining previous and parsed candidates in one pass per side. A fingerprint becomes an anchor only when it occurs exactly once on both sides. This prevents repeated paragraphs or headings from being matched arbitrarily.

### 3. Restore order with LIS

Sort anchors by previous index, map them to parsed indices, and compute the longest increasing subsequence of parsed indices using binary search. The resulting ordered anchors preserve unchanged block IDs without a two-dimensional dynamic-programming matrix.

Expected complexity is O(n log n) time and O(n) memory.

### 4. Reconcile bounded gaps conservatively

Between ordered anchors, reconcile only small gaps with the existing compatibility rules. Local dynamic programming is permitted only when both gap dimensions are below a fixed small limit. Larger gaps use conservative same-position/type matching only when the correspondence is unambiguous; otherwise new IDs remain in place.

This bounds worst-case work and keeps the rule that a missed ID is safer than assigning an ID to the wrong block.

## Correctness Requirements

- Existing stable IDs survive ordinary insertion, deletion, and editing around unchanged blocks.
- `ai-summary`, `key-points`, `questions`, and `timestamp-outline` remain tied to the correct semantic sections.
- Duplicate semantic headings before or after the original section do not steal stable IDs.
- Indistinguishable duplicate sections receive no semantic stable ID.
- Repeated ordinary fingerprints are never matched arbitrarily merely because their text is equal.
- No internal ID markers are added to user Markdown or persisted storage.

## Performance Requirement

A deterministic 3,000-block reconciliation benchmark in Vitest must complete in at most 50 ms after a warm-up run. The test data must include insertions and deletions so it exercises reconciliation rather than a trivial empty or identical fast path.

To reduce CI noise, the benchmark should measure only the reconciliation call, use a generous platform-independent failure message, and avoid asserting sub-millisecond differences. If repository CI proves too variable for a hard wall-clock assertion, retain a separate algorithmic guard that prevents allocating a global quadratic matrix and use the 50 ms benchmark in the local verification script.

## Testing

1. Add the 3,000-block performance regression first and confirm it fails against the current matrix implementation.
2. Preserve all existing adapter and AI overwrite tests.
3. Add repeated ordinary fingerprint coverage to prove the new unique-anchor rule does not guess.
4. Run focused adapter tests, all video-note tests, lint, TypeScript/build, and the repository verification script.

## Non-goals

- Changing Markdown syntax or storage format.
- Virtualizing the editor or changing React rendering behavior.
- Optimizing notes substantially larger than 3,000 blocks beyond maintaining bounded memory and near-linear matching.
