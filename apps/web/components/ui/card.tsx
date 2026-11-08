import type { LucideIcon } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "bg-card text-card-foreground border-border rounded-xl border p-5",
        className,
      )}
      {...props}
    />
  );
}

// Luma card parts: an icon tile, a title and a muted line under it, and an optional action at the end.
export function CardHeader({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn("flex items-start gap-3", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: ComponentProps<"h2">) {
  return (
    <h2
      data-slot="card-title"
      className={cn("text-base leading-snug font-semibold", className)}
      {...props}
    />
  );
}

export function CardDescription({ className, ...props }: ComponentProps<"p">) {
  return (
    <p
      data-slot="card-description"
      className={cn("text-muted-foreground text-sm", className)}
      {...props}
    />
  );
}

// Decorative: the heading beside it carries the meaning.
export function IconTile({
  icon: Icon,
  className,
}: {
  icon: LucideIcon;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "bg-muted text-foreground grid size-9 shrink-0 place-items-center rounded-lg",
        className,
      )}
    >
      <Icon className="size-4" />
    </span>
  );
}

// An inner box: bordered on a light card, a muted fill on a dark one. Muted text on the light muted fill
// measures under 4.5:1, so the light box has no fill.
export const INNER_BOX =
  "rounded-lg border p-3 dark:border-transparent dark:bg-muted";
