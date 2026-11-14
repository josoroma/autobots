/**
 * One automated accessibility scan for every suite (TWEB-05). The only module that imports
 * @axe-core/playwright, so each scan applies the same pass line and reports failures the same way.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

type Violation = Awaited<
  ReturnType<AxeBuilder["analyze"]>
>["violations"][number];

/** WCAG 2.1 A and AA, the pass line the browser suites' scans apply (Decision 0010). */
export const WCAG_PASS_LINE = [
  "wcag2a",
  "wcag2aa",
  "wcag21a",
  "wcag21aa",
] as const;

/**
 * WCAG 2.2 AA, which the scans that already selected it keep. Applying it everywhere would extend
 * Decision 0010, which is the owner's call.
 */
export const WCAG_22_AA = ["wcag22aa"] as const;

export interface ScanOptions {
  /** Tags applied on top of the pass line, such as WCAG_22_AA. */
  extraTags?: readonly string[];
}

/** The page's violations at the pass line, plus any extra tags. */
export async function scanA11y(
  page: Page,
  { extraTags = [] }: ScanOptions = {},
): Promise<Violation[]> {
  const results = await new AxeBuilder({ page })
    .withTags([...WCAG_PASS_LINE, ...extraTags])
    .analyze();
  return results.violations;
}

/** A violation as its rule, impact and first three elements, which is what a failure needs. */
export function describeViolation(violation: Violation): string {
  const targets = violation.nodes
    .slice(0, 3)
    .map((node) => node.target.join(" "))
    .join(", ");
  return `${violation.id} (${violation.impact ?? "no impact"}): ${targets}`;
}

/** Asserts the page has no violation at the pass line, plus any extra tags. */
export async function expectNoA11yViolations(
  page: Page,
  { extraTags = [], label }: ScanOptions & { label?: string } = {},
): Promise<void> {
  const violations = await scanA11y(page, { extraTags });
  expect(violations.map(describeViolation), label ?? page.url()).toEqual([]);
}
