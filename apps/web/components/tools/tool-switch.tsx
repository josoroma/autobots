"use client";

import { cn } from "@/lib/utils";

/**
 * An owner's on/off switch for a tool or a group in this workspace (Decision 0033 W5). It is a
 * native button with `role="switch"`, so a keyboard reaches it and a screen reader announces its
 * state. Its words say On or Off, so the state is never carried by the track's color alone (DS-04).
 */
export function ToolSwitch({
  label,
  on,
  disabled,
  onToggle,
}: {
  /** The accessible name, such as "Google Crawl for this workspace". */
  label: string;
  on: boolean;
  disabled: boolean;
  onToggle: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onToggle(!on)}
      data-field="switch"
      className="text-ui focus-visible:outline-ring inline-flex items-center gap-2 rounded-md disabled:opacity-60"
    >
      <span
        aria-hidden="true"
        className={cn(
          "border-border relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors",
          on ? "bg-primary" : "bg-muted",
        )}
      >
        <span
          className={cn(
            "bg-background inline-block size-4 rounded-full shadow-sm transition-transform",
            on ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </span>
      <span>{on ? "On" : "Off"}</span>
    </button>
  );
}
