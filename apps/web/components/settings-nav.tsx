"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const SECTIONS = [
  { href: "/settings", label: "Appearance" },
  { href: "/settings/notifications", label: "Notifications" },
  { href: "/settings/account", label: "Account" },
  { href: "/settings/data", label: "Data on this Mac" },
  { href: "/settings/keyboard", label: "Keyboard" },
] as const;

const ELSEWHERE = [
  { href: "/settings/models", label: "Models" },
  { href: "/operations", label: "Operations" },
] as const;

const ITEM =
  "text-foreground/85 hover:bg-accent block rounded-md px-2.5 py-1.5 text-[13px]";

export function SettingsNav() {
  const path = usePathname();
  return (
    <nav
      aria-label="Settings sections"
      className="border-border flex min-w-0 flex-wrap items-center gap-x-6 gap-y-2 border-b pb-3"
    >
      <ul data-field="settings-sections" className="flex flex-wrap gap-1">
        {SECTIONS.map((section) => {
          const here = path === section.href;
          return (
            <li key={section.href}>
              <Link
                href={section.href}
                aria-current={here ? "page" : undefined}
                className={cn(
                  ITEM,
                  here && "bg-accent text-foreground font-medium",
                )}
              >
                {section.label}
              </Link>
            </li>
          );
        })}
      </ul>
      <span className="text-muted-foreground text-[11.5px] font-medium">
        Also in Settings
      </span>
      <ul data-field="settings-elsewhere" className="flex flex-wrap gap-1">
        {ELSEWHERE.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={cn(ITEM, "inline-flex items-center gap-1")}
            >
              {item.label}
              <ArrowUpRight
                aria-hidden="true"
                className="text-muted-foreground size-3.5"
              />
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
