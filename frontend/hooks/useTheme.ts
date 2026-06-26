"use client";

import { useCallback, useEffect, useState } from "react";

const THEME_STORAGE_KEY = "theme";

const getInitialDarkMode = () => {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(THEME_STORAGE_KEY) !== "light";
};

const getInitialReady = () => typeof window !== "undefined";

export function useTheme() {
  const [isDarkMode, setIsDarkMode] = useState(getInitialDarkMode);
  const [ready] = useState(getInitialReady);

  useEffect(() => {
    if (typeof window === "undefined" || !ready) return;
    if (isDarkMode) {
      document.documentElement.classList.remove("light");
      localStorage.setItem(THEME_STORAGE_KEY, "dark");
    } else {
      document.documentElement.classList.add("light");
      localStorage.setItem(THEME_STORAGE_KEY, "light");
    }
  }, [isDarkMode, ready]);

  const toggleTheme = useCallback(() => {
    setIsDarkMode((value) => !value);
  }, []);

  return { isDarkMode, ready, setIsDarkMode, toggleTheme };
}

export function useForceDarkTheme() {
  useEffect(() => {
    const wasLightMode = document.documentElement.classList.contains("light");
    document.documentElement.classList.remove("light");
    document.documentElement.classList.add("auth-page-active");
    document.body.classList.add("auth-page-active");

    return () => {
      document.documentElement.classList.remove("auth-page-active");
      document.body.classList.remove("auth-page-active");
      if (wasLightMode) {
        document.documentElement.classList.add("light");
      }
    };
  }, []);
}
