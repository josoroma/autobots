import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

// A small uppercase label over a value. Uppercase is styling only, so the text itself is unchanged.
export function Eyebrow({ className, ...props }: ComponentProps<"span">) {
  return (
    <span
      data-slot="eyebrow"
      className={cn(
        "text-muted-foreground text-xs font-medium tracking-wider uppercase",
        className,
      )}
      {...props}
    />
  );
}
