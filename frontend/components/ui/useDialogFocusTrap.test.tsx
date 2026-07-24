import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useDialogFocusTrap } from "./useDialogFocusTrap";

afterEach(cleanup);

function FocusTrapHarness() {
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstRef = useRef<HTMLButtonElement>(null);
  useDialogFocusTrap({
    containerRef: dialogRef,
    initialFocusRef: firstRef,
    onEscape: vi.fn(),
  });
  return (
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="trap">
      <button ref={firstRef}>first</button>
      <button>middle</button>
      <details>
        <summary tabIndex={0}>closed summary</summary>
        <button>closed details action</button>
      </details>
      <div hidden>
        <button>hidden ancestor</button>
      </div>
      <div aria-hidden="true">
        <button>aria hidden ancestor</button>
      </div>
      <div inert>
        <button>inert ancestor</button>
      </div>
      <button hidden>hidden self</button>
      <div style={{ display: "none" }}>
        <button>display none ancestor</button>
      </div>
      <div style={{ visibility: "hidden" }}>
        <button>visibility hidden ancestor</button>
      </div>
    </div>
  );
}

describe("useDialogFocusTrap", () => {
  it("wraps among semantic visible controls and ignores closed details content", () => {
    render(<FocusTrapHarness />);
    const first = screen.getByRole("button", { name: "first" });
    const last = screen.getByText("closed summary");
    expect(first).toHaveFocus();

    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(first).toHaveFocus();

    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });

  it("does not focus a dialog inside a hidden ancestor", () => {
    render(
      <div aria-hidden="true">
        <FocusTrapHarness />
      </div>,
    );
    expect(screen.getByText("first")).not.toHaveFocus();
  });
});
