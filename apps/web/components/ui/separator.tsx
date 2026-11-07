import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

// Decorative, so assistive technology skips it.
export function Separator({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="separator"
      role="none"
      className={cn("bg-border h-px w-full shrink-0", className)}
      {...props}
    />
  );
}
