"use client";

import {
  Activity,
  Cpu,
  House,
  Play,
  Settings,
  ShieldCheck,
  UsersRound,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

interface Item {
  href: string;
  label: string;
  icon: LucideIcon;
}

// Decision 0021 R5: the same nine links, grouped by what the person is doing. Tools stays directly before Settings (Decision 0017 C9).
const GROUPS: { label: string | null; items: Item[] }[] = [
  {
    label: null,
    items: [
      { href: "/", label: "Home", icon: House },
      { href: "/runs", label: "Runs", icon: Play },
      { href: "/approvals", label: "Approvals", icon: ShieldCheck },
    ],
  },
  {
    label: "Build",
    items: [
      { href: "/experts", label: "Experts", icon: UsersRound },
      { href: "/workflows", label: "Workflows", icon: Workflow },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/operations", label: "Operations", icon: Activity },
      { href: "/settings/models", label: "Models", icon: Cpu },
      { href: "/tools", label: "Tools", icon: Wrench },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

const HREFS = GROUPS.flatMap((group) => group.items.map((item) => item.href));

// The longest matching entry is the current one, so /settings/models marks Models and not Settings.
function current(pathname: string): string | undefined {
  return HREFS.filter(
    (href) =>
      pathname === href || (href !== "/" && pathname.startsWith(`${href}/`)),
  ).sort((a, b) => b.length - a.length)[0];
}

// The current page is marked by its fill, its weight and aria-current, not by color alone.
export function SidebarNav() {
  const active = current(usePathname());
  return (
    <div className="space-y-4">
      {GROUPS.map(({ label, items }) => (
        <div key={label ?? "work"} className="space-y-1">
          {label ? (
            <p
              id={`nav-${label.toLowerCase()}`}
              className="text-muted-foreground px-3 pb-1 text-xs font-semibold tracking-wide"
            >
              {label}
            </p>
          ) : null}
          <ul
            className="space-y-0.5"
            aria-labelledby={label ? `nav-${label.toLowerCase()}` : undefined}
          >
            {items.map(({ href, label: text, icon: Icon }) => {
              const here = href === active;
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={here ? "page" : undefined}
                    className={cn(
                      "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-sidebar-ring text-sidebar-foreground flex h-9 items-center gap-3 rounded-lg px-3 text-sm",
                      here &&
                        "bg-sidebar-accent text-sidebar-accent-foreground font-medium",
                    )}
                  >
                    <Icon
                      aria-hidden="true"
                      className={cn(
                        "size-4 shrink-0",
                        here ? "text-sidebar-primary" : "text-muted-foreground",
                      )}
                    />
                    {text}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
