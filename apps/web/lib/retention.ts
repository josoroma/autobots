/**
 * A retention window as typed in Operations: empty keeps everything, otherwise whole days only.
 * A lenient parse saved "1,000" as 1 day, which feeds an irreversible retention pass (WSYS-01).
 * The contract's range and the cross-field rule are checked elsewhere; this refuses malformed text.
 */
export type Days = { valid: true; days: number | null } | { valid: false };

export function parseDays(text: string): Days {
  const value = text.trim();
  if (value === "") return { valid: true, days: null };
  if (!/^\d+$/.test(value)) return { valid: false };
  const days = Number(value);
  return Number.isSafeInteger(days) ? { valid: true, days } : { valid: false };
}
