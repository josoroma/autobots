import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { ThemeProvider } from "@/components/theme-provider";
import { WaitingNotifier } from "@/components/waiting-notifier";
import { beforePaintScript } from "@/lib/preferences";

import "./globals.css";

// WSYS-17: each page's title names it in the tab and the history, then the app.
export const metadata: Metadata = {
  title: { default: "Autobots", template: "%s · Autobots" },
};

// DS-02 and PRD-Studio SE-03: the theme guard and the presentation preferences, applied before paint
// from the one preference table in lib/preferences.ts.
const BEFORE_PAINT = beforePaintScript();

// The dark class is the server's fallback. The theme script replaces it before paint only for a saved
// light choice, or System on a light OS, so suppression stays limited to this root element's attributes.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: BEFORE_PAINT }} />
      </head>
      <body>
        <ThemeProvider>
          <AppShell>{children}</AppShell>
          <WaitingNotifier />
        </ThemeProvider>
      </body>
    </html>
  );
}
