import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** One choice: its words and, once known, its count. */
export interface Segment<T extends string> {
  id: T;
  label: ReactNode;
  /** Shown after the words with a space. Undefined shows neither the space nor the count. */
  count?: ReactNode;
  disabled?: boolean;
}

// DS-03 and DS-04: one pressed button among a few, on the muted track, with the pressed one on the page
// surface. `compact` is the small toggle inside a bordered header, such as Fields and JSON.
const SIZES = {
  default: {
    group: "bg-muted/60 inline-flex w-fit gap-0.5 rounded-lg p-[3px]",
    item: "text-foreground/80 inline-flex h-7 items-center gap-1.5 rounded-md border border-transparent px-3 text-ui disabled:opacity-50",
    pressed:
      "bg-background text-foreground border-border font-medium dark:bg-accent",
  },
  compact: {
    group: "flex gap-1",
    item: "rounded-md border border-transparent px-2 py-0.5 disabled:opacity-60",
    pressed: "border-border bg-background dark:bg-accent",
  },
} as const;

/**
 * Tabs with counts as `aria-pressed` buttons in a labelled group (WTAP-11). `dataKey` names the
 * attribute that carries each choice's id, such as `data-tab`, which the browser suites read.
 */
export function SegmentedControl<T extends string>({
  label,
  items,
  value,
  onChange,
  dataKey,
  wrap = false,
  size = "default",
}: {
  label: string;
  items: readonly Segment<T>[];
  value: T;
  onChange: (id: T) => void;
  dataKey?: string;
  wrap?: boolean;
  size?: keyof typeof SIZES;
}) {
  const style = SIZES[size];
  return (
    <div
      role="group"
      aria-label={label}
      className={cn(style.group, wrap && "flex-wrap")}
    >
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          {...(dataKey === undefined ? {} : { [`data-${dataKey}`]: item.id })}
          aria-pressed={value === item.id}
          disabled={item.disabled}
          onClick={() => onChange(item.id)}
          className={cn(style.item, value === item.id && style.pressed)}
        >
          {item.label}
          {item.count === undefined ? null : (
            <>
              {" "}
              <span className="tabular-nums">{item.count}</span>
            </>
          )}
        </button>
      ))}
    </div>
  );
}
