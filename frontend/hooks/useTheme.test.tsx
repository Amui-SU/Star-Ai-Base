import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useForceDarkTheme, useTheme } from "@/hooks/useTheme";

function ThemeHarness() {
  const { isDarkMode, ready, toggleTheme } = useTheme();

  return (
    <button type="button" onClick={toggleTheme}>
      {ready ? (isDarkMode ? "dark" : "light") : "loading"}
    </button>
  );
}

function ForceDarkHarness() {
  useForceDarkTheme();
  return <div>auth</div>;
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  localStorage.clear();
  document.documentElement.className = "";
  document.body.className = "";
});

describe("theme hooks", () => {
  it("persists the app theme and mirrors it to the document class", async () => {
    localStorage.setItem("theme", "light");
    const user = userEvent.setup();

    render(<ThemeHarness />);

    expect(await screen.findByRole("button", { name: "light" })).toBeVisible();
    await waitFor(() => {
      expect(document.documentElement).toHaveClass("light");
    });

    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "dark" })).toBeVisible();
    });
    expect(document.documentElement).not.toHaveClass("light");
    expect(localStorage.getItem("theme")).toBe("dark");
  });

  it("becomes ready without waiting for pending timers", async () => {
    vi.useFakeTimers();
    localStorage.setItem("theme", "light");

    render(<ThemeHarness />);

    await act(async () => {});

    expect(screen.getByRole("button", { name: "light" })).toBeVisible();
  });

  it("forces auth screens to dark mode and restores previous light mode", () => {
    document.documentElement.classList.add("light");

    const { unmount } = render(<ForceDarkHarness />);

    expect(document.documentElement).toHaveClass("auth-page-active");
    expect(document.body).toHaveClass("auth-page-active");
    expect(document.documentElement).not.toHaveClass("light");

    unmount();

    expect(document.documentElement).not.toHaveClass("auth-page-active");
    expect(document.body).not.toHaveClass("auth-page-active");
    expect(document.documentElement).toHaveClass("light");
  });
});
