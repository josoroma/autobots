import Link from "next/link";
import type { ReactNode } from "react";

const NAVIGATION = [
  { href: "/", label: "Home" },
  { href: "/runs", label: "Runs" },
  { href: "/experts", label: "Experts" },
  { href: "/approvals", label: "Approvals" },
  { href: "/operations", label: "Operations" },
  { href: "/workflows", label: "Workflows" },
  { href: "/settings", label: "Settings" },
  { href: "/settings/models", label: "Models" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <a
        href="#content"
        className="bg-primary text-primary-foreground sr-only rounded-md px-3 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-10"
      >
        Skip to content
      </a>
      <nav
        aria-label="Main"
        className="bg-sidebar text-sidebar-foreground border-sidebar-border w-full shrink-0 space-y-1 border-b p-4 md:w-56 md:border-r md:border-b-0"
      >
        <p className="px-3 pb-3 text-sm font-semibold">Autobots</p>
        {NAVIGATION.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-sidebar-ring block rounded-md px-3 py-2 text-sm"
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <main id="content" className="min-w-0 flex-1 p-4 md:p-8">
        {children}
      </main>
    </div>
  );
}
