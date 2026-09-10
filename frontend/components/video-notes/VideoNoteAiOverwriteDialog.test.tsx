import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import VideoNoteAiOverwriteDialog from "./VideoNoteAiOverwriteDialog";

it("names the overwrite dialog, focuses cancel first, and cancels on Escape", async () => {
  const user = userEvent.setup();
  const onCancel = vi.fn();

  render(
    <VideoNoteAiOverwriteDialog
      targets={["摘要", "关键观点"]}
      onCancel={onCancel}
      onConfirm={vi.fn()}
    />,
  );

  const dialog = screen.getByRole("dialog", { name: "覆盖现有内容？" });
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(screen.getByRole("button", { name: "取消" })).toHaveFocus();
  expect(dialog).toHaveTextContent("摘要");
  expect(dialog).toHaveTextContent("关键观点");

  await user.keyboard("{Escape}");
  expect(onCancel).toHaveBeenCalledTimes(1);
});
