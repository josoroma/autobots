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

const NAVIGATION: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/", label: "Home", icon: House },
  { href: "/runs", label: "Runs", icon: Play },
  { href: "/experts", label: "Experts", icon: UsersRound },
  { href: "/approvals", label: "Approvals", icon: ShieldCheck },
  { href: "/operations", label: "Operations", icon: Activity },
  { href: "/workflows", label: "Workflows", icon: Workflow },
  { href: "/tools", label: "Tools", icon: Wrench },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/settings/models", label: "Models", icon: Cpu },
];

// The longest matching entry is the current one, so /settings/models marks Models and not Settings.
function current(pathname: string): string | undefined {
  return NAVIGATION.map((item) => item.href)
    .filter(
      (href) =>
        pathname === href || (href !== "/" && pathname.startsWith(`${href}/`)),
    )
    .sort((a, b) => b.length - a.length)[0];
}

// The current page is marked by its fill, its weight and aria-current, not by color alone.
export function SidebarNav() {
  const active = current(usePathname());
  return (
    <ul className="space-y-1">
      {NAVIGATION.map(({ href, label, icon: Icon }) => {
        const here = href === active;
        return (
          <li key={href}>
            <Link
              href={href}
              aria-current={here ? "page" : undefined}
              className={cn(
                "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-sidebar-ring flex items-center gap-3 rounded-xl px-3 py-2 text-sm",
                here &&
                  "bg-sidebar-accent text-sidebar-accent-foreground font-semibold",
              )}
            >
              <Icon
                aria-hidden="true"
                className={cn(
                  "size-4 shrink-0",
                  here ? "text-sidebar-primary" : "text-muted-foreground",
                )}
              />
              {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
