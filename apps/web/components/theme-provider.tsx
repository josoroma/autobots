"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

// DS-02: dark by default whatever the OS prefers. An old `system` value resolves to dark.
export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      themes={["dark", "light"]}
      storageKey="autobots.theme"
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
