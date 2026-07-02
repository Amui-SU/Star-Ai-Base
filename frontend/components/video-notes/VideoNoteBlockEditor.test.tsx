import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import VideoNoteBlockEditor from "./VideoNoteBlockEditor";
import type { VideoNoteBlock } from "@/lib/api";

afterEach(() => {
  cleanup();
});

describe("VideoNoteBlockEditor", () => {
  it("edits, adds, removes, and reorders note blocks", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    let blocks: VideoNoteBlock[] = [
      { id: "h1", type: "heading", level: 1, text: "标题" },
      { id: "p1", type: "paragraph", text: "第一段" },
    ];

    const { rerender } = render(
      <VideoNoteBlockEditor blocks={blocks} onChange={onChange} />,
    );

    fireEvent.change(screen.getByLabelText("编辑块 h1"), {
      target: { value: "新标题" },
    });
    blocks = onChange.mock.calls.at(-1)?.[0] as VideoNoteBlock[];
    expect(blocks[0].text).toBe("新标题");

    rerender(<VideoNoteBlockEditor blocks={blocks} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "添加段落" }));
    blocks = onChange.mock.calls.at(-1)?.[0] as VideoNoteBlock[];
    expect(blocks).toHaveLength(3);

    rerender(<VideoNoteBlockEditor blocks={blocks} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "上移块 p1" }));
    blocks = onChange.mock.calls.at(-1)?.[0] as VideoNoteBlock[];
    expect(blocks.map((block) => block.id).slice(0, 2)).toEqual(["p1", "h1"]);

    rerender(<VideoNoteBlockEditor blocks={blocks} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "删除块 h1" }));
    blocks = onChange.mock.calls.at(-1)?.[0] as VideoNoteBlock[];
    expect(blocks.map((block) => block.id)).not.toContain("h1");
  });
});
