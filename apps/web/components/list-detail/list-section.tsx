import type { ReactNode } from "react";

import { SectionLabel } from "@/components/ui/page-header";

/** A list's own sentence for no items at all, or none matching. */
function EmptyList({ children }: { children: ReactNode }) {
  return (
    <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
      {children}
    </p>
  );
}

/**
 * A Studio list's frame, which the Experts and Workflows screens share (WBLD-09): its heading, its
 * toolbar, then the list, or the sentence for no items at all or none matching, then its footer.
 */
export function ListSection({
  heading,
  toolbar,
  total,
  shown,
  empty,
  noMatch,
  footer,
  className,
  children,
}: {
  heading: string;
  toolbar: ReactNode;
  /** How many items there are, and how many the filter shows. */
  total: number;
  shown: number;
  empty: string;
  noMatch: string;
  footer?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby="list-heading" className={className}>
      <SectionLabel id="list-heading">{heading}</SectionLabel>
      {toolbar}
      {total === 0 ? (
        <EmptyList>{empty}</EmptyList>
      ) : shown === 0 ? (
        <EmptyList>{noMatch}</EmptyList>
      ) : (
        children
      )}
      {footer}
    </section>
  );
}
