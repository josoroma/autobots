import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** One of Operations' boxed sections, named by its heading when `id` is given. */
export function OperationsBox({
  id,
  icon: Icon,
  heading,
  children,
}: {
  id?: string;
  icon: LucideIcon;
  heading: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className="border-border space-y-3 rounded-xl border px-5 py-4"
    >
      <h2 id={id} className="flex items-center gap-2 text-sm font-semibold">
        <Icon
          aria-hidden="true"
          className="text-muted-foreground size-4 shrink-0"
        />
        {heading}
      </h2>
      {children}
    </section>
  );
}

export const BOX_LIST = "divide-border divide-y border-t text-sm";
