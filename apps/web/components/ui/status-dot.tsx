import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Decision 0021 R4: a state's dot only repeats the words beside it, so it is hidden from assistive
// technology. `current` takes the color of the text around it; `idle` is a ring, not a fill.
const statusDotVariants = cva("inline-block shrink-0 rounded-full", {
  variants: {
    tone: {
      current: "bg-current",
      live: "bg-live-text ring-live-text/20 ring-3",
      success: "bg-success-text",
      attention: "bg-attention",
      danger: "bg-destructive",
      muted: "bg-muted-foreground",
      idle: "border-muted-foreground border-[1.5px]",
    },
    size: {
      sm: "size-1.5",
      md: "size-dot",
    },
  },
  defaultVariants: { tone: "current", size: "sm" },
});

export type StatusDotTone = NonNullable<
  VariantProps<typeof statusDotVariants>["tone"]
>;

export function StatusDot({
  tone,
  size,
  className,
}: VariantProps<typeof statusDotVariants> & { className?: string }) {
  return (
    <span
      aria-hidden="true"
      data-slot="status-dot"
      className={cn(statusDotVariants({ tone, size }), className)}
    />
  );
}
