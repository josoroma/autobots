import { Zap } from "lucide-react";
import type { ReactNode } from "react";

import { AccountFooter } from "@/components/account-footer";
import { HealthLine } from "@/components/readiness";
import { SidebarNav } from "@/components/sidebar-nav";
import { fetchPendingApprovals, fetchReadiness } from "@/lib/service-status";

// Decision 0021 and PRD-Studio SH-05: the Studio frame. A quiet sidebar with the grouped sections
// and an account footer that names the person and says where the app runs. Home holds the goal composer, so the first link after the skip link is Home.
// Pages own their width and padding inside <main>.
async function ShellNav() {
  return <SidebarNav pending={await fetchPendingApprovals()} />;
}

async function ShellHealth() {
  return <HealthLine readiness={await fetchReadiness()} />;
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <a
        href="#content"
        className="bg-primary text-primary-foreground sr-only rounded-lg px-3 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-10"
      >
        Skip to content
      </a>
      <aside className="bg-sidebar text-sidebar-foreground border-sidebar-border w-full shrink-0 border-b md:w-[252px] md:border-r md:border-b-0">
        <div className="flex flex-col gap-3 px-3 py-4 md:sticky md:top-0 md:h-screen">
          <p className="flex items-center gap-2.5 px-2 pb-1">
            <span
              aria-hidden="true"
              className="bg-sidebar-primary text-sidebar-primary-foreground grid size-6 place-items-center rounded-md"
            >
              <Zap className="size-3.5" strokeWidth={2.25} />
            </span>
            <span className="font-serif text-lg tracking-tight">Autobots</span>
          </p>
          <nav aria-label="Main" className="pt-1">
            <ShellNav />
          </nav>
          <div className="mt-auto space-y-3">
            <ShellHealth />
            <AccountFooter />
          </div>
        </div>
      </aside>
      <main id="content" className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-9">
        {children}
      </main>
    </div>
  );
}
