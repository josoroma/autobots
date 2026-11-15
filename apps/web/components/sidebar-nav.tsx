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

import { currentHref } from "@/lib/nav";
import { cn } from "@/lib/utils";

interface Item {
  href: string;
  label: string;
  icon: LucideIcon;
  /** A count shown beside the link: the approvals waiting for a decision (PRD-Studio SH-03). */
  count?: "pending";
}

// PRD-Studio SH-01 and Decision 0022 D2: the same nine links, grouped by what the person is doing,
// with Tools under Build directly after Workflows.
const GROUPS: { label: string; shown: boolean; items: Item[] }[] = [
  {
    // Named for assistive technology; the concepts draw this first group without a heading.
    label: "Work",
    shown: false,
    items: [
      { href: "/", label: "Home", icon: House },
      { href: "/runs", label: "Runs", icon: Play },
      {
        href: "/approvals",
        label: "Approvals",
        icon: ShieldCheck,
        count: "pending",
      },
    ],
  },
  {
    label: "Build",
    shown: true,
    items: [
      { href: "/experts", label: "Experts", icon: UsersRound },
      { href: "/workflows", label: "Workflows", icon: Workflow },
      { href: "/tools", label: "Tools", icon: Wrench },
    ],
  },
  {
    label: "System",
    shown: true,
    items: [
      { href: "/operations", label: "Operations", icon: Activity },
      { href: "/settings/models", label: "Models", icon: Cpu },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

const HREFS = GROUPS.flatMap((group) => group.items.map((item) => item.href));

function PendingBadge({ count }: { count: number }) {
  return (
    <span
      data-approvals-badge
      className="bg-attention text-attention-foreground ml-auto grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-tag font-semibold tabular-nums"
    >
      {count}
      <span className="sr-only"> waiting</span>
    </span>
  );
}

// The current page is marked by its fill, its weight and aria-current, not by color alone.
function NavItem({
  item,
  here,
  pending,
}: {
  item: Item;
  here: boolean;
  pending: number | null;
}) {
  const Icon = item.icon;
  const count = item.count === "pending" ? pending : null;
  return (
    <li>
      <Link
        href={item.href}
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
        {item.label}
        {count !== null && count > 0 ? (
          <>
            {" "}
            <PendingBadge count={count} />
          </>
        ) : null}
      </Link>
    </li>
  );
}

export function SidebarNav({ pending = null }: { pending?: number | null }) {
  const active = currentHref(usePathname(), HREFS);
  return (
    <div className="space-y-4">
      {GROUPS.map(({ label, shown, items }) => (
        <div key={label} className="space-y-1">
          <p
            id={`nav-${label.toLowerCase()}`}
            className={cn(
              "text-muted-foreground px-3 pb-1 text-xs font-semibold tracking-wide",
              !shown && "sr-only",
            )}
          >
            {label}
          </p>
          <ul
            className="space-y-0.5"
            aria-labelledby={`nav-${label.toLowerCase()}`}
          >
            {items.map((item) => (
              <NavItem
                key={item.href}
                item={item}
                here={item.href === active}
                pending={pending}
              />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
