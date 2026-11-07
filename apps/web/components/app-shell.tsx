import { Bot } from "lucide-react";
import type { ReactNode } from "react";

import { SidebarNav } from "@/components/sidebar-nav";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <a
        href="#content"
        className="bg-primary text-primary-foreground sr-only rounded-4xl px-3 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-10"
      >
        Skip to content
      </a>
      <nav
        aria-label="Main"
        className="bg-sidebar text-sidebar-foreground border-sidebar-border w-full shrink-0 space-y-4 border-b p-4 md:w-60 md:border-r md:border-b-0"
      >
        <p className="flex items-center gap-2 px-3 pt-1 text-sm font-semibold">
          <span
            aria-hidden="true"
            className="bg-sidebar-primary text-sidebar-primary-foreground grid size-7 place-items-center rounded-xl"
          >
            <Bot className="size-4" />
          </span>
          Autobots
        </p>
        <SidebarNav />
      </nav>
      <main id="content" className="min-w-0 flex-1 p-4 md:p-8">
        {children}
      </main>
    </div>
  );
}
