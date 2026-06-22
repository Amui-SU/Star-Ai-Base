"use client";

import { useEffect } from "react";
import { App } from "@capacitor/app";
import {
  applyLaunchConnectionFromLocation,
  parseLocalConnectionUrl,
  saveLocalConnection,
} from "@/lib/localConnection";

export default function LocalConnectionBootstrap() {
  useEffect(() => {
    applyLaunchConnectionFromLocation();
    const handle = App.addListener("appUrlOpen", (event) => {
      const apiBaseUrl = parseLocalConnectionUrl(event.url);
      if (apiBaseUrl) saveLocalConnection(apiBaseUrl);
    });
    return () => {
      void handle.then((listener) => listener.remove());
    };
  }, []);

  return null;
}
