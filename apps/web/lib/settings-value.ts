/**
 * Which value a settings panel shows: a write's accepted reply, or its read (WSYS-03). The reply is
 * stamped when it arrives, so a read that settled before then, even one started after the press,
 * never hides it, and a read that settles after it shows. Pure and JSX-free, so `node --test`
 * covers it.
 */

/** A write's accepted reply, stamped in epoch milliseconds when it arrived. */
export interface Written<T> {
  at: number;
  value: T;
}

/**
 * The reply, unless a read settled after it arrived. Within the same millisecond the reply is kept,
 * since that read can't be shown to have seen the write.
 */
export function shownValue<T>(
  read: T | null,
  readAt: number | null,
  written: Written<T> | null,
): T | null {
  if (written === null) return read;
  return readAt !== null && readAt > written.at ? read : written.value;
}
