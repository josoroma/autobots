// Decision 0023 E2: Operations' schema line, the applied migrations read against the ones this
// version ships. Pure, so it can be tested without a browser.
const count = new Intl.NumberFormat("en");

export function schemaValue(applied: number | null, shipped: number): string {
  return applied === null
    ? `${count.format(shipped)} migrations in this version, and no readable history.`
    : `${count.format(applied)} of ${count.format(shipped)} migrations applied.`;
}
