/**
 * Keyboard rules shared by the shortcuts (PRD-Studio SH-02, Decision 0022 D3, WCMP-10). Pure and
 * JSX-free, so `node --test` covers what it can without a document.
 */

// Decision 0022 D3: no shortcut acts while focus is in a text field.
export function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
  );
}

/** The parts of a key press a shortcut reads. A shortcut that needs Shift or the key's position reads those too. */
export interface KeyPress {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
  shiftKey?: boolean;
  code?: string;
}

/**
 * The option an arrow moves to among `count`, wrapping at both ends. Any other key, or an empty
 * list, leaves it where it is.
 */
export function moveActive(
  current: number,
  key: string,
  count: number,
): number {
  if (count === 0) return current;
  if (key === "ArrowDown") return (current + 1) % count;
  if (key === "ArrowUp") return (current - 1 + count) % count;
  return current;
}
