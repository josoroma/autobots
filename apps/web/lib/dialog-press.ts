/**
 * When a click closes a modal dialog (Decision 0026 G2). A click on the backdrop reaches the dialog
 * element itself, outside its box. A press that begins inside and is released over the backdrop, such
 * as selecting text in Search's field, also ends on the dialog element, so the press is checked too:
 * only a press and a release both outside the box close it. Pure, so `node --test` covers it.
 */

/** A dialog's box in viewport coordinates. */
export interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** Where a press or a release happened: on the dialog element itself, and outside its box. */
export interface Spot {
  onDialog: boolean;
  outside: boolean;
}

export function spotOf(
  box: Box,
  point: { x: number; y: number },
  onDialog: boolean,
): Spot {
  const outside =
    point.x < box.left ||
    point.x > box.right ||
    point.y < box.top ||
    point.y > box.bottom;
  return { onDialog, outside };
}

/** Whether a release closes the dialog, given where its press began, if one was seen. */
export function closesDialog(press: Spot | null, release: Spot): boolean {
  return (
    press !== null &&
    press.onDialog &&
    press.outside &&
    release.onDialog &&
    release.outside
  );
}
