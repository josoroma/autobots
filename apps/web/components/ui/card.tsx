import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "bg-card text-card-foreground border-border rounded-lg border p-6",
        className,
      )}
      {...props}
    />
  );
}
