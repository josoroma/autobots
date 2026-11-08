import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

// A pill label. Its words carry the meaning; a dot or icon only repeats it, never replaces it.
// Tones (Decision 0021 R3–R4): live, success, attention and danger color the words, measured at 4.5:1.
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap [&>svg]:size-3.5",
  {
    variants: {
      variant: {
        secondary: "bg-secondary text-secondary-foreground border-transparent",
        outline: "text-foreground border-border",
        muted: "text-muted-foreground border-border",
        live: "text-live-text border-live-text/35 dark:bg-live-text/10",
        success:
          "text-success-text border-success-text/35 dark:bg-success-text/10",
        attention: "text-attention border-attention/40 dark:bg-attention/10",
        danger: "text-destructive border-destructive/35 dark:bg-destructive/10",
      },
    },
    defaultVariants: { variant: "outline" },
  },
);

export function Badge({
  className,
  variant,
  dot = false,
  children,
  ...props
}: ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { dot?: boolean }) {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    >
      {dot ? (
        <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      ) : null}
      {children}
    </span>
  );
}
