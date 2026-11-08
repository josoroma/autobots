import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

// Decision 0021: every section opens the same way. A serif title, one muted line, and actions on the right.
export function PageHeader({
  title,
  description,
  actions,
  className,
  titleId,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  titleId?: string;
}) {
  return (
    <header
      data-slot="page-header"
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0 space-y-1.5">
        <h1 id={titleId} className="text-[32px] leading-tight">
          {title}
        </h1>
        {description ? (
          <p className="text-muted-foreground max-w-2xl text-[14.5px] leading-relaxed">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      ) : null}
    </header>
  );
}

// A thin label above a group of content, in the interface sans.
export function SectionLabel({
  className,
  children,
  id,
  as: Tag = "h2",
}: {
  className?: string;
  children: ReactNode;
  id?: string;
  as?: "h2" | "h3" | "p";
}) {
  return (
    <Tag
      id={id}
      className={cn(
        "text-muted-foreground text-xs font-semibold tracking-wide",
        className,
      )}
    >
      {children}
    </Tag>
  );
}
