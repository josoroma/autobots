import type { ReactNode } from "react";

// Decision 0021: a hairline-separated section in place of a card, with an optional muted line under its heading.
export function InspectorSection({
  id,
  title,
  note,
  children,
}: {
  id: string;
  title: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3 border-t pt-6">
      <div className="space-y-1">
        <h2 id={id} className="text-sm font-semibold">
          {title}
        </h2>
        {note === undefined ? null : (
          <p className="text-muted-foreground text-sm">{note}</p>
        )}
      </div>
      {children}
    </section>
  );
}
