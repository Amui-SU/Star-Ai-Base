import { useEffect, useRef, type RefObject } from "react";

const focusableSelector = [
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[href]",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function focusableElements(container: HTMLElement) {
  return Array.from(
    container.querySelectorAll<HTMLElement>(focusableSelector),
  ).filter((element) => isSemanticallyVisible(element, container));
}

function isSemanticallyVisible(element: HTMLElement, container: HTMLElement) {
  let current: HTMLElement | null = element;
  let insideContainer = false;
  while (current) {
    if (current === container) insideContainer = true;
    const inert = (current as HTMLElement & { inert?: boolean }).inert;
    if (
      current.hidden ||
      current.getAttribute("aria-hidden") === "true" ||
      current.hasAttribute("inert") ||
      inert
    )
      return false;
    const style = window.getComputedStyle(current);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (current instanceof HTMLDetailsElement && !current.open) {
      const summary = Array.from(current.children).find(
        (child) => child instanceof HTMLElement && child.tagName === "SUMMARY",
      );
      if (!summary?.contains(element)) return false;
    }
    current = current.parentElement;
  }
  return insideContainer;
}

export function useDialogFocusTrap({
  active = true,
  containerRef,
  initialFocusRef,
  onEscape,
}: {
  active?: boolean;
  containerRef: RefObject<HTMLElement | null>;
  initialFocusRef?: RefObject<HTMLElement | null>;
  onEscape: () => void;
}) {
  const escapeRef = useRef(onEscape);
  useEffect(() => {
    escapeRef.current = onEscape;
  }, [onEscape]);

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;
    const previous = document.activeElement as HTMLElement | null;
    const initial = initialFocusRef?.current;
    (initial && isSemanticallyVisible(initial, container)
      ? initial
      : (focusableElements(container)[0] ?? container)
    ).focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const owner = target.closest<HTMLElement>(
        '[role="dialog"][aria-modal="true"]',
      );
      if (owner && owner !== container) return;
      if (event.key === "Escape") {
        event.preventDefault();
        escapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = focusableElements(container);
      if (!focusable.length) {
        event.preventDefault();
        container.focus();
        return;
      }
      const current = document.activeElement;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (
        event.shiftKey &&
        (current === first || !container.contains(current))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (current === last || !container.contains(current))
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (previous?.isConnected) previous.focus();
    };
  }, [active, containerRef, initialFocusRef]);
}
