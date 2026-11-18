/**
 * PRD-Studio AP-04: ⌘↵ or ⌘⌫ (Ctrl on other systems), pressed twice within 2 s, decides the selected
 * request. WTAP-02: a held key's repeated keydown is not a second press, an Alt chord is not a
 * shortcut, and an arm belongs to one request, so a reload that changes the selection can't carry
 * it to another. While a decision is in flight no press arms or decides, since the write it asked
 * for would send nothing until the first settles (Decision 0027 D2).
 */
export type Decision = "approve" | "reject";

export interface Arm {
  decision: Decision;
  approvalId: string;
  until: number;
}

export interface Chord {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
}

export const ARM_MS = 2_000;

/** The decision a key chord asks for, or null when it isn't one. */
export function chord(event: Chord): Decision | null {
  if (!(event.metaKey || event.ctrlKey) || event.altKey) return null;
  if (event.key === "Enter") return "approve";
  if (event.key === "Backspace") return "reject";
  return null;
}

export type Press =
  | { kind: "ignore" }
  | { kind: "too_large" }
  | { kind: "arm"; arm: Arm }
  | { kind: "decide"; decision: Decision };

/** What one press does, given the current arm. */
export function press(
  arm: Arm | null,
  input: {
    decision: Decision;
    approvalId: string;
    truncated: boolean;
    repeat: boolean;
    /** A decision is in flight. */
    pending: boolean;
    now: number;
  },
): Press {
  if (input.repeat || input.pending) return { kind: "ignore" };
  if (input.decision === "approve" && input.truncated) {
    return { kind: "too_large" };
  }
  if (
    arm !== null &&
    arm.decision === input.decision &&
    arm.approvalId === input.approvalId &&
    input.now <= arm.until
  ) {
    return { kind: "decide", decision: input.decision };
  }
  return {
    kind: "arm",
    arm: {
      decision: input.decision,
      approvalId: input.approvalId,
      until: input.now + ARM_MS,
    },
  };
}
