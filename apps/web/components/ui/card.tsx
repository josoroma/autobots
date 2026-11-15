import { cva, type VariantProps } from "class-variance-authority";
import type { LucideIcon } from "lucide-react";
import { type ComponentProps, createElement } from "react";

import { cn } from "@/lib/utils";

/** The elements a card can be, so a list item or a form takes the card's surface itself (WSHL-12). */
type CardProps =
  | ({ as?: "section" } & ComponentProps<"section">)
  | ({ as: "div" } & ComponentProps<"div">)
  | ({ as: "li" } & ComponentProps<"li">)
  | ({ as: "ul" } & ComponentProps<"ul">)
  | ({ as: "form" } & ComponentProps<"form">)
  | ({ as: "article" } & ComponentProps<"article">);

// DS-03: panels and cards use the card pair. A section unless `as` names another element.
export function Card({ as = "section", className, ...props }: CardProps) {
  return createElement(as, {
    "data-slot": "card",
    className: cn(
      "bg-card text-card-foreground border-border rounded-xl border p-5",
      className,
    ),
    ...props,
  });
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

// Decision 0021 R5: `display` is the serif title of a card or dialog that heads its own content.
const cardTitleVariants = cva("", {
  variants: {
    size: {
      default: "text-base leading-snug font-semibold",
      display:
        "font-serif text-display leading-tight font-normal tracking-tight",
    },
  },
  defaultVariants: { size: "default" },
});

export function CardTitle({
  className,
  size,
  ...props
}: ComponentProps<"h2"> & VariantProps<typeof cardTitleVariants>) {
  return (
    <h2
      data-slot="card-title"
      className={cn(cardTitleVariants({ size }), className)}
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

// A name's first letter on a tile, such as an Expert's. Decorative: the name is said beside it.
export function InitialTile({
  initial,
  className,
}: {
  initial: string;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "bg-background grid shrink-0 place-items-center rounded-lg border font-serif dark:border-transparent dark:bg-muted",
        className,
      )}
    >
      {initial}
    </span>
  );
}

// An inner box: bordered on a light card, a muted fill on a dark one. Muted text on the light muted fill
// measures under 4.5:1, so the light box has no fill.
export const INNER_BOX =
  "rounded-lg border p-3 dark:border-transparent dark:bg-muted";
