import type { VideoNoteBlock, VideoNoteBlockItem } from "@/lib/api";

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
  if (typeof timestamp !== "number" || !Number.isFinite(timestamp)) return text;
  return `[${formatTimestamp(timestamp)}] ${text}`.trim();
}

function formatTimestamp(seconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
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

function resolveBlockId(
  blockIndex: number,
  previousBlocks: VideoNoteBlock[],
): string {
  return previousBlocks[blockIndex]?.id ?? createMarkdownBlockId();
}

function createParsedBlock(
  parsedBlocks: VideoNoteBlock[],
  type: VideoNoteBlock["type"],
  previousBlocks: VideoNoteBlock[],
  values: Omit<VideoNoteBlock, "id" | "type"> = {},
): VideoNoteBlock {
  return {
    id: resolveBlockId(parsedBlocks.length, previousBlocks),
    type,
    ...values,
  };
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
        createParsedBlock(parsedBlocks, "heading", previousBlocks, {
          level: heading[1].length,
          text: heading[2].trim(),
        }),
      );
      index += 1;
      continue;
    }

    if (isDivider(line)) {
      parsedBlocks.push(
        createParsedBlock(parsedBlocks, "divider", previousBlocks),
      );
      index += 1;
      continue;
    }

    const task = matchTask(line);
    if (task) {
      while (index < lines.length) {
        const taskMatch = matchTask(lines[index]);
        if (!taskMatch) break;
        parsedBlocks.push(
          createParsedBlock(parsedBlocks, "todo", previousBlocks, {
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
          parsedBlocks,
          timestampItems.length === items.length
            ? "timestamp_outline"
            : "bulleted_list",
          previousBlocks,
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
        createParsedBlock(parsedBlocks, "quote", previousBlocks, {
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
      createParsedBlock(parsedBlocks, "paragraph", previousBlocks, {
        text: paragraphLines.join("\n").trim(),
      }),
    );
  }

  return parsedBlocks;
}
