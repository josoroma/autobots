import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

export const metadata = {
  title: "Autobots",
};

// next-themes would apply any saved value as a class, so `garbage` would render the light tokens. This runs
// first, and only ever removes a theme that is not an allowed choice. It also applies the presentation
// preferences (PRD-Studio SE-03) before paint, reading only the exact values the Settings page writes.
// Storage that can't be read changes nothing, so the page stays dark and comfortable.
const BEFORE_PAINT = `try{var s=localStorage,k="autobots.theme",v=s.getItem(k);if(v!==null&&v!=="dark"&&v!=="light"&&v!=="system")s.removeItem(k);var d=document.documentElement;if(s.getItem("autobots.serif")==="off")d.dataset.serif="off";if(s.getItem("autobots.density")==="compact")d.dataset.density="compact";if(s.getItem("autobots.motion")==="reduce")d.dataset.motion="reduce"}catch(e){}`;

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
        </ThemeProvider>
      </body>
    </html>
  );
}
