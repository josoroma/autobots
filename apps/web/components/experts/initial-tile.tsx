import { initialOf } from "@/lib/experts/card";
import { cn } from "@/lib/utils";

/** An Expert's first letter on a tile. Decorative: its name is said beside it. */
export function InitialTile({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "bg-background grid shrink-0 place-items-center rounded-[10px] border font-serif dark:border-transparent dark:bg-muted",
        className,
      )}
    >
      {initialOf(name)}
    </span>
  );
}
