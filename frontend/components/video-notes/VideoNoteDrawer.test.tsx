import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import VideoNoteDrawer from "./VideoNoteDrawer";

const rect = (width: number) =>
  ({
    bottom: 0,
    height: 800,
    left: 0,
    right: width,
    top: 0,
    width,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  }) as DOMRect;

afterEach(() => {
  localStorage.clear();
  document.documentElement.style.removeProperty("--video-note-drawer-width");
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
});

describe("VideoNoteDrawer", () => {
  it("resizes from the right edge on desktop", () => {
    const { container } = render(
      <div data-testid="workspace">
        <VideoNoteDrawer fullscreen={false}>
          <div>note body</div>
        </VideoNoteDrawer>
      </div>,
    );

    const workspace = screen.getByTestId("workspace");
    const drawer = container.querySelector(".video-note-drawer") as HTMLElement;
    workspace.getBoundingClientRect = () => rect(1200);
    drawer.getBoundingClientRect = () => rect(620);

    fireEvent.mouseDown(
      screen.getByRole("separator", { name: "调整笔记宽度" }),
      {
        clientX: 620,
      },
    );
    fireEvent.mouseMove(window, { clientX: 760 });
    fireEvent.mouseUp(window);

    expect(drawer.style.getPropertyValue("--video-note-drawer-width")).toBe(
      "760px",
    );
    expect(
      document.documentElement.style.getPropertyValue(
        "--video-note-drawer-width",
      ),
    ).toBe("760px");
    expect(localStorage.getItem("video_note_drawer_width")).toBe("760");
  });

  it("clears the shared drawer width variable when closed", () => {
    const { unmount } = render(
      <VideoNoteDrawer fullscreen={false}>
        <div>note body</div>
      </VideoNoteDrawer>,
    );

    expect(
      document.documentElement.style.getPropertyValue(
        "--video-note-drawer-width",
      ),
    ).toBe("720px");

    unmount();

    expect(
      document.documentElement.style.getPropertyValue(
        "--video-note-drawer-width",
      ),
    ).toBe("");
  });
});
