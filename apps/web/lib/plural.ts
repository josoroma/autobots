/**
 * A count with its noun, singular for exactly one, so no screen says "1 hours ago" (WSYS-10).
 * Pure and JSX-free, so `node --test` covers it.
 */
export function counted(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}
