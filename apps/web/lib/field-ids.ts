/**
 * The ids that tie a control to its help and error text (DH-06, DS-04, WSYS-12). Pure, so `node --test`
 * covers it; components/ui/field.tsx re-exports both.
 */

/** The ids of a control's description and error, derived from the control's own id. */
export function fieldIds(id: string): { description: string; error: string } {
  return { description: `${id}-description`, error: `${id}-error` };
}

/**
 * The ids of what describes a control, joined for `aria-describedby`, so a screen reader reads the
 * help or the error on reaching the control. Undefined when nothing describes it.
 */
export function describedBy(
  ...ids: readonly (string | false | null | undefined)[]
): string | undefined {
  const present = ids.filter(
    (id): id is string => typeof id === "string" && id !== "",
  );
  return present.length === 0 ? undefined : present.join(" ");
}
