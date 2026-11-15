// PRD-Studio SE-07: every keyboard shortcut the app offers, in one place. Settings → Keyboard lists
// these, so a shortcut added elsewhere is added here too.
import type { KeyPress } from "./keyboard.ts";

export type Shortcut = { keys: string[]; action: string };
export type ShortcutGroup = { where: string; shortcuts: Shortcut[] };

/** A listed shortcut with how a key press is recognised and how aria-keyshortcuts names it. */
export interface BoundShortcut extends Shortcut {
  aria: string;
  matches: (event: KeyPress) => boolean;
}

/**
 * PRD-Studio SR-01 and SH-02: ⌘K, or Ctrl+K, opens search. The palette's matcher, its
 * aria-keyshortcuts and its key hint all read this one definition (WCMP-10).
 */
export const SEARCH_SHORTCUT: BoundShortcut = {
  keys: ["⌘", "K"],
  action: "Search runs, Experts, workflows and tools. Ctrl works for ⌘",
  aria: "Meta+K Control+K",
  matches: (event) =>
    (event.metaKey || event.ctrlKey) &&
    !event.altKey &&
    event.key.toLowerCase() === "k",
};

/**
 * PRD-Studio SH-02 and Decision 0022 D16: ⇧⌘O, or Shift+Ctrl+O, opens Home's composer. It matches
 * the O key by `code`, which Shift doesn't change. The button, its hint and Settings → Keyboard read
 * this one definition (XWEB-18).
 */
export const NEW_RUN_SHORTCUT: BoundShortcut = {
  keys: ["⇧", "⌘", "O"],
  action: "Open Home's composer with focus in the goal. Ctrl works for ⌘",
  aria: "Shift+Meta+O Shift+Control+O",
  matches: (event) =>
    event.shiftKey === true &&
    (event.metaKey || event.ctrlKey) &&
    !event.altKey &&
    event.code === "KeyO",
};

export const SHORTCUTS: ShortcutGroup[] = [
  {
    where: "Anywhere",
    shortcuts: [NEW_RUN_SHORTCUT, SEARCH_SHORTCUT],
  },
  {
    where: "Approvals",
    shortcuts: [
      { keys: ["J"], action: "Select the next request" },
      { keys: ["K"], action: "Select the previous request" },
      {
        keys: ["↓", "↑"],
        action: "Move through the list while it has focus",
      },
      {
        keys: ["⌘", "↵"],
        action:
          "Approve the selected request: press twice within 2 seconds. Ctrl works for ⌘",
      },
      {
        keys: ["⌘", "⌫"],
        action:
          "Reject the selected request: press twice within 2 seconds. Ctrl works for ⌘",
      },
    ],
  },
  {
    where: "Every page",
    shortcuts: [
      {
        keys: ["Tab"],
        action:
          "The first press offers Skip to content, which moves past the sidebar",
      },
    ],
  },
];
