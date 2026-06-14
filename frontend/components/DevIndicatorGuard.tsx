"use client";

import { useEffect } from "react";

export function DevIndicatorGuard() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "development") {
      return;
    }

    const hideIndicator = () => {
      document.querySelectorAll("nextjs-portal").forEach((portal) => {
        const root = portal.shadowRoot;
        root
          ?.getElementById("data-devtools-indicator")
          ?.setAttribute("style", "display: none !important;");
        root
          ?.querySelector(".dev-tools-indicator-menu")
          ?.setAttribute("style", "display: none !important;");
      });
    };

    hideIndicator();

    const observer = new MutationObserver(hideIndicator);
    observer.observe(document.body, { childList: true, subtree: true });

    return () => observer.disconnect();
  }, []);

  return null;
}
