import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

export const metadata = {
  title: "Autobots",
};

// next-themes would apply any saved value as a class, so `garbage` or an old `system` would render
// the light tokens. This runs first, and only ever removes a value that is not an allowed choice.
const DROP_INVALID_THEME = `try{var k="autobots.theme",v=localStorage.getItem(k);if(v!==null&&v!=="dark"&&v!=="light")localStorage.removeItem(k)}catch(e){}`;

// The dark class is the server's fallback. The theme script replaces it before paint only for a
// saved light choice, so suppression stays limited to this root element's attributes.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: DROP_INVALID_THEME }} />
      </head>
      <body>
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
