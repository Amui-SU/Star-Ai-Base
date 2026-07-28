import type { VideoNoteBlock, VideoNoteBlockItem } from "@/lib/api";
import { formatVideoNoteTime } from "./videoNoteTime";
import { alignUniqueFingerprints } from "./videoNoteSequenceAlignment";

const createMarkdownBlockId = () =>
  `md-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const listLikeTypes = new Set([
  "bulleted_list",
  "key_points",
  "questions",
  "timestamp_outline",
]);

function textValue(value: unknown): string {
  return String(value ?? "").trim();
}

function itemText(item: VideoNoteBlockItem): string {
  const text = textValue(item.text ?? item.content);
  const timestamp = item.timestamp ?? item.time;
  if (timestamp === undefined || timestamp === null) return text;
  return `[${formatVideoNoteTime(timestamp)}] ${text}`.trim();
}

function blockToMarkdown(block: VideoNoteBlock): string {
  if (block.type === "heading") {
    const level = Math.min(6, Math.max(1, Math.floor(block.level ?? 2)));
    return `${"#".repeat(level)} ${textValue(block.text)}`.trim();
  }

  if (block.type === "todo") {
    const checked = block.checked ? "x" : " ";
    return `- [${checked}] ${textValue(block.text)}`.trimEnd();
  }

  if (block.type === "divider") return "---";

  if (block.type === "quote") {
    return textValue(block.text)
      .split("\n")
      .map((line) => `> ${line}`.trimEnd())
      .join("\n");
  }

  if (listLikeTypes.has(block.type)) {
    return (block.items ?? [])
      .map(itemText)
      .filter(Boolean)
      .map((text) => `- ${text}`)
      .join("\n");
  }

  return textValue(block.text);
}

export function blocksToMarkdown(blocks: VideoNoteBlock[]): string {
  return blocks.map(blockToMarkdown).filter(Boolean).join("\n\n");
}

function createParsedBlock(
  type: VideoNoteBlock["type"],
  values: Omit<VideoNoteBlock, "id" | "type"> = {},
): VideoNoteBlock {
  return {
    id: createMarkdownBlockId(),
    type,
    ...values,
  };
}

const semanticSections = [
  {
    heading: "AI 摘要",
    titleIds: ["ai-summary-title"],
    contentIds: ["ai-summary"],
  },
  {
    heading: "关键观点",
    titleIds: ["key-points-title"],
    contentIds: ["key-points"],
  },
  {
    heading: "时间戳提纲",
    titleIds: ["timestamp-title"],
    contentIds: ["timestamp-outline"],
  },
  {
    heading: "我的笔记",
    titleIds: ["my-notes-title"],
    contentIds: ["my-notes"],
  },
  {
    heading: "问题与待办",
    titleIds: ["questions-title"],
    contentIds: ["questions", "ai-review-questions"],
  },
] as const;

function reconciliationKind(block: VideoNoteBlock) {
  if (block.type === "heading") return "heading";
  if (listLikeTypes.has(block.type) || block.items) return "list";
  if (block.type === "ai_summary" || block.type === "paragraph") return "text";
  return block.type;
}

function blockFingerprint(block: VideoNoteBlock) {
  const markdown = blockToMarkdown(block).trim();
  return markdown ? `${reconciliationKind(block)}\u0000${markdown}` : null;
}

interface BlockIdAssignment {
  id: string;
  previousIndex: number;
}

function reconcileBlockIds(
  parsedBlocks: VideoNoteBlock[],
  previousBlocks: VideoNoteBlock[],
) {
  if (parsedBlocks.length === 0 || previousBlocks.length === 0) {
    return parsedBlocks;
  }

  const parsedFingerprints = parsedBlocks.map(blockFingerprint);
  const previousFingerprints = previousBlocks.map(blockFingerprint);
  const previousIndexById = new Map(
    previousBlocks.map((block, index) => [block.id, index]),
  );
  const assignments = new Map<number, BlockIdAssignment>();
  const usedPreviousIndices = new Set<number>();
  const assign = (parsedIndex: number, candidateIds: readonly string[]) => {
    if (assignments.has(parsedIndex)) return;
    const id = candidateIds.find((candidate) => {
      const previousIndex = previousIndexById.get(candidate);
      return (
        previousIndex !== undefined && !usedPreviousIndices.has(previousIndex)
      );
    });
    if (!id) return;
    const previousIndex = previousIndexById.get(id);
    if (previousIndex === undefined) return;
    assignments.set(parsedIndex, { id, previousIndex });
    usedPreviousIndices.add(previousIndex);
  };

  const ambiguousSections: Array<{
    section: (typeof semanticSections)[number];
    headingIndices: number[];
  }> = [];
  const ambiguousParsedHeadingIndices = new Set<number>();
  const ambiguousParsedContentIndices = new Set<number>();
  const ambiguousPreviousHeadingIndices = new Set<number>();
  const ambiguousPreviousContentIndices = new Set<number>();

  for (const section of semanticSections) {
    const headingIndices = parsedBlocks
      .map((block, index) => ({ block, index }))
      .filter(
        ({ block }) =>
          block.type === "heading" && block.text?.trim() === section.heading,
      )
      .map(({ index }) => index);
    if (headingIndices.length > 1) {
      ambiguousSections.push({ section, headingIndices });
      headingIndices.forEach((index) =>
        ambiguousParsedHeadingIndices.add(index),
      );
      headingIndices.forEach((index) => {
        const contentIndex = index + 1;
        if (
          contentIndex < parsedBlocks.length &&
          parsedBlocks[contentIndex].type !== "heading"
        ) {
          ambiguousParsedContentIndices.add(contentIndex);
        }
      });
      section.titleIds.forEach((id) => {
        const previousIndex = previousIndexById.get(id);
        if (previousIndex !== undefined) {
          ambiguousPreviousHeadingIndices.add(previousIndex);
        }
      });
      section.contentIds.forEach((id) => {
        const previousIndex = previousIndexById.get(id);
        if (previousIndex !== undefined) {
          ambiguousPreviousContentIndices.add(previousIndex);
        }
      });
      continue;
    }
    const headingIndex = headingIndices[0];
    if (headingIndex === undefined) continue;
    assign(headingIndex, section.titleIds);
    const contentIndex = headingIndex + 1;
    if (
      contentIndex < parsedBlocks.length &&
      parsedBlocks[contentIndex].type !== "heading"
    ) {
      assign(contentIndex, section.contentIds);
    }
  }

  const previousCandidates = previousBlocks
    .map((_, index) => ({
      fingerprint: previousFingerprints[index],
      index,
    }))
    .filter(
      (candidate): candidate is { fingerprint: string; index: number } =>
        candidate.fingerprint !== null &&
        !ambiguousPreviousHeadingIndices.has(candidate.index) &&
        !ambiguousPreviousContentIndices.has(candidate.index) &&
        !usedPreviousIndices.has(candidate.index),
    );
  const parsedCandidates = parsedBlocks
    .map((_, index) => ({ fingerprint: parsedFingerprints[index], index }))
    .filter(
      (candidate): candidate is { fingerprint: string; index: number } =>
        candidate.fingerprint !== null &&
        !ambiguousParsedHeadingIndices.has(candidate.index) &&
        !ambiguousParsedContentIndices.has(candidate.index) &&
        !assignments.has(candidate.index),
    );
  for (const match of alignUniqueFingerprints(
    previousCandidates.map((candidate) => candidate.fingerprint),
    parsedCandidates.map((candidate) => candidate.fingerprint),
  )) {
    const previousCandidate = previousCandidates[match.previousIndex];
    const parsedCandidate = parsedCandidates[match.parsedIndex];
    assign(parsedCandidate.index, [previousBlocks[previousCandidate.index].id]);
  }

  for (const { section, headingIndices } of ambiguousSections) {
    const previousContentIndex = section.contentIds
      .map((id) => previousIndexById.get(id))
      .find((index): index is number => index !== undefined);
    if (previousContentIndex === undefined) continue;
    const previousContentFingerprint =
      previousFingerprints[previousContentIndex];
    if (!previousContentFingerprint) continue;

    const matchingHeadingIndices = headingIndices.filter((headingIndex) => {
      const contentIndex = headingIndex + 1;
      if (
        contentIndex >= parsedBlocks.length ||
        parsedBlocks[contentIndex].type === "heading" ||
        parsedFingerprints[contentIndex] !== previousContentFingerprint
      ) {
        return false;
      }
      return true;
    });
    if (matchingHeadingIndices.length !== 1) continue;

    const headingIndex = matchingHeadingIndices[0];
    assign(headingIndex, section.titleIds);
    assign(headingIndex + 1, section.contentIds);
  }

  const anchors = Array.from(assignments.entries())
    .map(([parsedIndex, assignment]) => ({ parsedIndex, ...assignment }))
    .sort((left, right) => left.parsedIndex - right.parsedIndex);
  const orderedAnchors: typeof anchors = [];
  const crossingParsedIndices = new Set<number>();
  const crossingPreviousIndices = new Set<number>();
  let lastPreviousIndex = -1;
  for (const anchor of anchors) {
    if (anchor.previousIndex <= lastPreviousIndex) {
      assignments.delete(anchor.parsedIndex);
      usedPreviousIndices.delete(anchor.previousIndex);
      crossingParsedIndices.add(anchor.parsedIndex);
      crossingPreviousIndices.add(anchor.previousIndex);
      continue;
    }
    orderedAnchors.push(anchor);
    lastPreviousIndex = anchor.previousIndex;
  }

  const fingerprintCounts = (candidates: typeof parsedCandidates) => {
    const counts = new Map<string, number>();
    for (const candidate of candidates) {
      counts.set(
        candidate.fingerprint,
        (counts.get(candidate.fingerprint) ?? 0) + 1,
      );
    }
    return counts;
  };
  const previousFingerprintCounts = fingerprintCounts(previousCandidates);
  const parsedFingerprintCounts = fingerprintCounts(parsedCandidates);
  const ambiguousFingerprints = new Set<string>();
  for (const [fingerprint, count] of previousFingerprintCounts) {
    if (count > 1) ambiguousFingerprints.add(fingerprint);
  }
  for (const [fingerprint, count] of parsedFingerprintCounts) {
    if (count > 1) ambiguousFingerprints.add(fingerprint);
  }

  const eligibleParsed = parsedCandidates.filter(
    (candidate) =>
      !assignments.has(candidate.index) &&
      !crossingParsedIndices.has(candidate.index) &&
      !ambiguousFingerprints.has(candidate.fingerprint),
  );
  const eligiblePrevious = previousCandidates.filter(
    (candidate) =>
      !usedPreviousIndices.has(candidate.index) &&
      !crossingPreviousIndices.has(candidate.index) &&
      !ambiguousFingerprints.has(candidate.fingerprint),
  );
  let parsedCursor = 0;
  let previousCursor = 0;
  for (const anchor of [
    ...orderedAnchors,
    {
      parsedIndex: parsedBlocks.length,
      previousIndex: previousBlocks.length,
      id: "",
    },
  ]) {
    const parsedGapStart = parsedCursor;
    while (
      parsedCursor < eligibleParsed.length &&
      eligibleParsed[parsedCursor].index < anchor.parsedIndex
    ) {
      parsedCursor += 1;
    }
    const previousGapStart = previousCursor;
    while (
      previousCursor < eligiblePrevious.length &&
      eligiblePrevious[previousCursor].index < anchor.previousIndex
    ) {
      previousCursor += 1;
    }

    const parsedGapLength = parsedCursor - parsedGapStart;
    const previousGapLength = previousCursor - previousGapStart;
    let compatible = parsedGapLength === previousGapLength;
    for (let offset = 0; compatible && offset < parsedGapLength; offset += 1) {
      const parsedCandidate = eligibleParsed[parsedGapStart + offset];
      const previousCandidate = eligiblePrevious[previousGapStart + offset];
      compatible =
        parsedCandidate.index === previousCandidate.index &&
        reconciliationKind(parsedBlocks[parsedCandidate.index]) ===
          reconciliationKind(previousBlocks[previousCandidate.index]);
    }
    if (compatible) {
      for (let offset = 0; offset < parsedGapLength; offset += 1) {
        const parsedCandidate = eligibleParsed[parsedGapStart + offset];
        const previousCandidate = eligiblePrevious[previousGapStart + offset];
        assign(parsedCandidate.index, [
          previousBlocks[previousCandidate.index].id,
        ]);
      }
    }
  }

  if (
    assignments.size === 0 &&
    ambiguousSections.length === 0 &&
    crossingParsedIndices.size === 0
  ) {
    const fallbackLength = Math.min(
      parsedCandidates.length,
      previousCandidates.length,
    );
    for (let index = 0; index < fallbackLength; index += 1) {
      const parsedCandidate = parsedCandidates[index];
      const previousCandidate = previousCandidates[index];
      if (
        ambiguousFingerprints.has(parsedCandidate.fingerprint) ||
        ambiguousFingerprints.has(previousCandidate.fingerprint)
      ) {
        continue;
      }
      if (
        reconciliationKind(parsedBlocks[parsedCandidate.index]) !==
        reconciliationKind(previousBlocks[previousCandidate.index])
      ) {
        break;
      }
      assign(parsedCandidate.index, [
        previousBlocks[previousCandidate.index].id,
      ]);
    }
  }

  return parsedBlocks.map((block, index) => ({
    ...block,
    id: assignments.get(index)?.id ?? block.id,
  }));
}

function isBlank(line: string): boolean {
  return line.trim().length === 0;
}

function isDivider(line: string): boolean {
  return /^-{3,}\s*$/.test(line.trim());
}

function matchHeading(line: string): RegExpMatchArray | null {
  return line.match(/^(#{1,6})\s+(.+)$/);
}

function matchTask(line: string): RegExpMatchArray | null {
  return line.match(/^[-*+]\s+\[([ xX])\]\s*(.*)$/);
}

function matchBullet(line: string): RegExpMatchArray | null {
  return line.match(/^[-*+]\s+(?!\[[ xX]\]\s*)(.*)$/);
}

function matchQuote(line: string): RegExpMatchArray | null {
  return line.match(/^>\s?(.*)$/);
}

function parseTimestampLiteral(value: string): number | null {
  const parts = value.split(":");
  if (parts.length < 2 || parts.length > 3) return null;
  const numbers = parts.map((part) => Number(part));
  if (numbers.some((part) => !Number.isFinite(part) || part < 0)) return null;
  return numbers.reduce((total, part) => total * 60 + Math.floor(part), 0);
}

function parseTimestampItem(value: string): VideoNoteBlockItem | null {
  const match = value.match(
    /^\[([0-9]+:[0-9]{1,2}(?::[0-9]{1,2})?)\](?:\([^)]+\))?\s*(.*)$/,
  );
  if (!match) return null;
  const time = parseTimestampLiteral(match[1]);
  if (time === null) return null;
  const text = match[2].trim();
  if (!text) return null;
  return { time, text };
}

export function markdownToVideoNoteBlocks(
  markdown: string,
  previousBlocks: VideoNoteBlock[] = [],
): VideoNoteBlock[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const parsedBlocks: VideoNoteBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (isBlank(line)) {
      index += 1;
      continue;
    }

    const heading = matchHeading(line);
    if (heading) {
      parsedBlocks.push(
        createParsedBlock("heading", {
          level: heading[1].length,
          text: heading[2].trim(),
        }),
      );
      index += 1;
      continue;
    }

    if (isDivider(line)) {
      parsedBlocks.push(createParsedBlock("divider"));
      index += 1;
      continue;
    }

    const task = matchTask(line);
    if (task) {
      while (index < lines.length) {
        const taskMatch = matchTask(lines[index]);
        if (!taskMatch) break;
        parsedBlocks.push(
          createParsedBlock("todo", {
            checked: taskMatch[1].toLowerCase() === "x",
            text: taskMatch[2].trim(),
          }),
        );
        index += 1;
      }
      continue;
    }

    const bullet = matchBullet(line);
    if (bullet) {
      const items: VideoNoteBlockItem[] = [];
      while (index < lines.length) {
        const bulletMatch = matchBullet(lines[index]);
        if (!bulletMatch) break;
        items.push({ text: bulletMatch[1].trim() });
        index += 1;
      }
      const timestampItems = items
        .map((item) => parseTimestampItem(textValue(item.text)))
        .filter((item): item is VideoNoteBlockItem => item !== null);
      parsedBlocks.push(
        createParsedBlock(
          timestampItems.length === items.length
            ? "timestamp_outline"
            : "bulleted_list",
          {
            items:
              timestampItems.length === items.length ? timestampItems : items,
          },
        ),
      );
      continue;
    }

    const quote = matchQuote(line);
    if (quote) {
      const quoteLines: string[] = [];
      while (index < lines.length) {
        const quoteMatch = matchQuote(lines[index]);
        if (!quoteMatch) break;
        quoteLines.push(quoteMatch[1]);
        index += 1;
      }
      parsedBlocks.push(
        createParsedBlock("quote", {
          text: quoteLines.join("\n").trim(),
        }),
      );
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length && !isBlank(lines[index])) {
      paragraphLines.push(lines[index].trimEnd());
      index += 1;
    }
    parsedBlocks.push(
      createParsedBlock("paragraph", {
        text: paragraphLines.join("\n").trim(),
      }),
    );
  }

  return reconcileBlockIds(parsedBlocks, previousBlocks);
}
