import { ChevronsUpDown } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { describedBy, fieldIds } from "@/lib/field-ids";
import { cn } from "@/lib/utils";

export { describedBy, fieldIds };

// Every form control in the app, DS-03: `input`, `border` and `ring`, with visible keyboard focus. Focus
// itself comes from `:focus-visible` in globals.css. `data-slot` lets a check tell these from a raw control.
// Studio shapes (Decision 0021): controls sit on the page surface in light and a muted fill in dark.
// Decision 0023 E1: one even border on all four sides, just at DS-03's 3:1, and no inset underline.
const CONTROL =
  "bg-background dark:bg-muted/60 text-foreground border-control block w-full border px-3 py-2 text-sm disabled:opacity-60";

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

// DS-04: a control's visible name. `data-slot` marks it as the shared one, as the controls are.
export function Label({ className, ...props }: ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn("text-sm font-medium", className)}
      {...props}
    />
  );
}

/** What a field gives its control: the id its label names, and what describes it. */
export interface FieldControl {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

/**
 * A label over its control, with optional help and error under it, each tied to the control through
 * `aria-describedby` and `aria-invalid` (DS-04, WSYS-12). The control is rendered by `children`, which
 * receives the props to spread on it.
 */
export function Field({
  id,
  label,
  description,
  error,
  className,
  children,
}: {
  id: string;
  label: ReactNode;
  description?: ReactNode;
  error?: ReactNode;
  className?: string;
  children: (control: FieldControl) => ReactNode;
}) {
  const ids = fieldIds(id);
  const hasError = error !== undefined && error !== null && error !== false;
  const described = describedBy(
    description !== undefined && ids.description,
    hasError && ids.error,
  );
  const control: FieldControl = {
    id,
    ...(described === undefined ? {} : { "aria-describedby": described }),
    ...(hasError ? { "aria-invalid": true as const } : {}),
  };
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children(control)}
      {description === undefined ? null : (
        <p
          id={ids.description}
          className="text-muted-foreground text-meta leading-relaxed"
        >
          {description}
        </p>
      )}
      {hasError ? (
        <p id={ids.error} role="alert" className="text-destructive text-meta">
          {error}
        </p>
      ) : null}
    </div>
  );
}
