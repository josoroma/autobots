/**
 * Pointer gestures for the suites that check how a modal dialog closes (Decision 0026 G2): a click on
 * the backdrop, a click inside the box, and a press inside dragged out over the backdrop.
 */
import type { Locator, Page } from "@playwright/test";

/** A point on a dialog's backdrop: the viewport's top-left corner, outside every dialog's box. */
export const BACKDROP = { x: 4, y: 4 } as const;

/** The element's box. A missing box means it isn't visible, which fails the test here. */
export async function boxOf(
  locator: Locator,
): Promise<{ x: number; y: number; width: number; height: number }> {
  const box = await locator.boundingBox();
  if (box === null)
    throw new Error("The element has no box, so it isn't visible.");
  return box;
}

/** Presses at the middle of `from`, moves to `to` and releases there, as a selection dragged out does. */
export async function dragOut(
  page: Page,
  from: Locator,
  to: { x: number; y: number },
): Promise<void> {
  const box = await boxOf(from);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(to.x, to.y, { steps: 4 });
  await page.mouse.up();
}
