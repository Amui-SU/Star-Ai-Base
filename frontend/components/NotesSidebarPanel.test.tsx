import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import NotesSidebarPanel from "@/components/NotesSidebarPanel";

afterEach(() => {
  cleanup();
});

describe("NotesSidebarPanel", () => {
  it("labels the editor and keeps the typed draft visible", async () => {
    const user = userEvent.setup();

    render(<NotesSidebarPanel />);

    expect(screen.getByRole("heading", { name: "笔记" })).toBeVisible();
    const editor = screen.getByRole("textbox", { name: "学习笔记" });
    expect(editor).toHaveAttribute("placeholder", "写下这次学习的要点");

    await user.type(editor, "第一条要点");

    expect(editor).toHaveValue("第一条要点");
  });

  it("opens the video note workspace from the notes sidebar", async () => {
    const user = userEvent.setup();
    const onOpenVideoNotes = vi.fn();

    render(<NotesSidebarPanel onOpenVideoNotes={onOpenVideoNotes} />);

    await user.click(screen.getByRole("button", { name: "打开视频笔记库" }));

    expect(onOpenVideoNotes).toHaveBeenCalledTimes(1);
  });
});
