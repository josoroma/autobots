import Link from "next/link";
import type { ReactNode } from "react";

const NAVIGATION = [
  { href: "/", label: "Home" },
  { href: "/settings", label: "Settings" },
  { href: "/settings/models", label: "Models" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <a
        href="#content"
        className="bg-primary text-primary-foreground sr-only rounded-md px-3 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-10"
      >
        Skip to content
      </a>
      <nav
        aria-label="Main"
        className="bg-sidebar text-sidebar-foreground border-sidebar-border w-56 space-y-1 border-r p-4"
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
      <main id="content" className="flex-1 p-8">
        {children}
      </main>
    </div>
  );
}
