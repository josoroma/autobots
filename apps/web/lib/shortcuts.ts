// PRD-Studio SE-07: every keyboard shortcut the app offers, in one place. Settings → Keyboard lists
// these, so a shortcut added elsewhere is added here too.
export type Shortcut = { keys: string[]; action: string };
export type ShortcutGroup = { where: string; shortcuts: Shortcut[] };

export const SHORTCUTS: ShortcutGroup[] = [
  {
    where: "Anywhere",
    shortcuts: [
      {
        keys: ["⇧", "⌘", "O"],
        action: "Open Home's composer with focus in the goal. Ctrl works for ⌘",
      },
      {
        keys: ["⌘", "K"],
        action: "Search runs, Experts, workflows and tools. Ctrl works for ⌘",
      },
    ],
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
