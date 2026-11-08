"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

// DS-02 as amended by Decision 0022 D2: dark for a first visit and for any missing, invalid or
// unreadable value, whatever the OS prefers. Only a person who picks System follows the OS.
export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      themes={["dark", "light"]}
      storageKey="autobots.theme"
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
