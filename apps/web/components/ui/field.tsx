import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

// Every form control in the app, DS-03: `input`, `border` and `ring`, with visible keyboard focus. Focus
// itself comes from `:focus-visible` in globals.css. `data-slot` lets a check tell these from a raw control.
const CONTROL =
  "bg-background text-foreground border-input control-boundary block w-full rounded-md border px-3 py-2 text-sm disabled:opacity-60";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return (
    <input data-slot="input" className={cn(CONTROL, className)} {...props} />
  );
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(CONTROL, className)}
      {...props}
    />
  );
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return (
    <select data-slot="select" className={cn(CONTROL, className)} {...props} />
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
