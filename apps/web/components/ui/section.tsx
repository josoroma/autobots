import type { LucideIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { SectionLabel } from "@/components/ui/page-header";
import { cn } from "@/lib/utils";

/**
 * Decision 0021 R1, the Studio layout: a hairline-separated section in place of a card, used on the run page and the run
 * inspector. Its heading names the region, and an optional muted line sits under it.
 */
export function HairlineSection({
  id,
  title,
  note,
  className,
  children,
  ...props
}: {
  id: string;
  title: ReactNode;
  note?: ReactNode;
} & Omit<ComponentProps<"section">, "id" | "title">) {
  const heading = (
    <h2 id={id} className="text-sm font-semibold">
      {title}
    </h2>
  );
  return (
    <section
      aria-labelledby={id}
      className={cn("space-y-3 border-t pt-6", className)}
      {...props}
    >
      {note === undefined ? (
        heading
      ) : (
        <div className="space-y-1">
          {heading}
          <p className="text-muted-foreground text-sm">{note}</p>
        </div>
      )}
      {children}
    </section>
  );
}

/**
 * Decision 0021 R1, the Studio layout: the head of one of Home's quiet hairline lists, an icon and a thin label with an
 * optional badge at the end. The section it heads is labelled by `id`.
 */
export function SectionHeading({
  icon: Icon,
  id,
  badge,
  children,
}: {
  icon: LucideIcon;
  id: string;
  badge?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <Icon
        aria-hidden="true"
        className="text-muted-foreground size-3.5 shrink-0"
      />
      <SectionLabel id={id} className="text-meta">
        {children}
      </SectionLabel>
      {badge}
    </div>
  );
}

// Decision 0021 R1, the Studio layout: a settings section, its label column on the left and its control
// on the right. `wide` is Account's layout, a 260px column and a 13px description. Both widths stay, by
// the owner's decision on R-68, since one width would visibly change a page (WSYS-15).
const SETTINGS_LAYOUT = {
  standard: {
    grid: "md:grid-cols-[minmax(0,240px)_minmax(0,1fr)] md:gap-7",
    label: "space-y-1",
    description: "text-meta leading-relaxed",
  },
  wide: {
    grid: "md:grid-cols-[260px_1fr]",
    label: undefined,
    description: "text-ui",
  },
} as const;

export function SettingsSection({
  id,
  title,
  description,
  layout = "standard",
  className,
  children,
  ...props
}: {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  layout?: keyof typeof SETTINGS_LAYOUT;
} & Omit<ComponentProps<"section">, "id" | "title">) {
  const style = SETTINGS_LAYOUT[layout];
  const heading = (
    <h2 id={id} className="text-sm font-semibold">
      {title}
    </h2>
  );
  return (
    <section
      aria-labelledby={id}
      className={cn(
        "border-border grid gap-4 border-t pt-5",
        style.grid,
        className,
      )}
      {...props}
    >
      {description === undefined ? (
        heading
      ) : (
        <div className={style.label}>
          {heading}
          <p className={cn("text-muted-foreground", style.description)}>
            {description}
          </p>
        </div>
      )}
      {children}
    </section>
  );
}
