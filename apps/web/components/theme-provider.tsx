"use client";

import { ThemeProvider as NextThemesProvider, useTheme } from "next-themes";
import { type ReactNode, useEffect, useSyncExternalStore } from "react";

import {
  NO_CHOICE,
  publishThemeChoice,
  subscribeThemeChoice,
  themeChoice,
  type ThemeChoice,
} from "@/lib/theme-choice";

/** Copies next-themes' choice into the store the appearance control reads (lib/theme-choice.ts). */
function ThemeBridge() {
  const { theme, setTheme } = useTheme();
  useEffect(() => {
    publishThemeChoice({ theme, setTheme });
  }, [theme, setTheme]);
  return null;
}

// DS-02 as amended by Decision 0022 D2: dark for a first visit and for any missing, invalid or
// unreadable value, whatever the OS prefers. Only a person who picks System follows the OS.
// next-themes applies the class, follows the OS for System and other tabs' changes from here. Its
// provider sits beside the app, not around it, so its context changing after mount never reaches
// a server-read section still waiting to hydrate (lib/theme-choice.ts).
export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <>
      <NextThemesProvider
        attribute="class"
        defaultTheme="dark"
        enableSystem
        themes={["dark", "light"]}
        storageKey="autobots.theme"
        disableTransitionOnChange
      >
        <ThemeBridge />
      </NextThemesProvider>
      {children}
    </>
  );
}

/** The chosen theme and the way to change it, for the appearance control. */
export function useThemeChoice(): ThemeChoice {
  return useSyncExternalStore(
    subscribeThemeChoice,
    themeChoice,
    () => NO_CHOICE,
  );
}
