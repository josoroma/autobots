import { ChevronsUpDown } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

// Every form control in the app, DS-03: `input`, `border` and `ring`, with visible keyboard focus. Focus
// itself comes from `:focus-visible` in globals.css. `data-slot` lets a check tell these from a raw control.
// Studio shapes (Decision 0021): controls sit on the page surface in light and a muted fill in dark.
const CONTROL =
  "bg-background dark:bg-muted/60 text-foreground border-input control-boundary block w-full border px-3 py-2 text-sm disabled:opacity-60";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      className={cn(CONTROL, "h-9 rounded-lg", className)}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(CONTROL, "rounded-xl", className)}
      {...props}
    />
  );
}

// The native element keeps its own menu, keyboard and form behavior; only its trigger is drawn here.
export function Select({ className, ...props }: ComponentProps<"select">) {
  return (
    <span className="relative block">
      <select
        data-slot="select"
        className={cn(
          CONTROL,
          "h-9 appearance-none rounded-lg pr-9",
          className,
        )}
        {...props}
      />
      <ChevronsUpDown
        aria-hidden="true"
        className="text-muted-foreground pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2"
      />
    </span>
  );
}

export function Choice({
  className,
  type = "radio",
  ...props
}: Omit<ComponentProps<"input">, "type"> & { type?: "radio" | "checkbox" }) {
  return (
    <input
      data-slot="choice"
      type={type}
      className={cn("accent-primary size-4", className)}
      {...props}
    />
  );
}
