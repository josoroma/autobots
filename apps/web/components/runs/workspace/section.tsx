import type { ReactNode } from "react";

// Decision 0021: a hairline-separated section in place of a card. Its heading names the region.
export function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3 border-t pt-6">
      <h2 id={id} className="text-sm font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}
