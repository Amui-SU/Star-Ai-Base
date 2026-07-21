import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Composer from "@/components/chat/Composer";
import { EMPTY_CHAT_SCOPE } from "@/lib/chatScope";

function renderComposer() {
  const onInputChange = vi.fn();
  const onSend = vi.fn();

  render(
    <Composer
      inputRef={{ current: null }}
      input=""
      knowledgeBaseId={null}
      isGenerating={false}
      canSend={false}
      scopeOptions={{ folders: [] }}
      chatScope={EMPTY_CHAT_SCOPE}
      webSearchEnabled={false}
      webSearchProvider="auto"
      webSearchConfig={null}
      canConfigureWebSearch={false}
      webSearchNotice=""
      onInputChange={onInputChange}
      onSend={onSend}
      onStopGenerating={vi.fn()}
      onScopeChange={vi.fn()}
      onWebSearchChange={vi.fn()}
      onWebSearchProviderChange={vi.fn()}
      onConfigureTavily={vi.fn()}
    />,
  );

  return { onInputChange, onSend };
}

describe("Composer interactions without a selected knowledge base", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("keeps the question input focusable", () => {
    renderComposer();

    const input = screen.getByRole("textbox");
    input.focus();

    expect(input).toBeEnabled();
    expect(input).toHaveFocus();
  });

  it("does not submit on Enter while sending is unavailable", () => {
    const { onSend } = renderComposer();

    fireEvent.keyDown(screen.getByRole("textbox"), {
      key: "Enter",
      shiftKey: false,
    });

    expect(onSend).not.toHaveBeenCalled();
  });
});
