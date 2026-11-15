/**
 * The inbox's keys (PRD-Studio AP-02, AP-04): J and K move, as do the arrows while focus is in the
 * list, and ⌘↵ or ⌘⌫ pressed twice within 2 s decides the selected waiting request. The two-press
 * rule is `lib/approval-shortcut.ts` (R-16); this hook holds the arm, says what it means and lapses
 * it. Nothing acts while a person is typing. The listener is subscribed once and reads the newest
 * render through an effect event.
 */
import type { ApprovalView } from "@autobots/api-client";
import { useCallback, useEffect, useEffectEvent, useState } from "react";

import { chord, press, type Arm, type Decision } from "@/lib/approval-shortcut";
import { armedText, NOTHING_DECIDED, TOO_LARGE } from "@/lib/approval-text";
import { typing } from "@/lib/keyboard";

export interface ShortcutInputs {
  /** The requests shown, in their order. */
  approvals: readonly ApprovalView[];
  selected: string | null;
  /** The selected request, when it's shown. */
  current: ApprovalView | null;
  /** Only a waiting request can be decided. */
  waiting: boolean;
  select: (id: string) => void;
  decide: (approval: ApprovalView, decision: Decision) => void;
}

export interface Shortcuts {
  /** What the newest press means, for the polite live region. */
  announcement: string;
  /** Forgets a first press, such as when the selection or the tab changes. */
  disarm: () => void;
}

// The request one step from the selected one, held at either end of the list.
function neighbour(
  approvals: readonly ApprovalView[],
  selected: string | null,
  step: 1 | -1,
): ApprovalView | undefined {
  const index = approvals.findIndex((item) => item.id === selected);
  return approvals[Math.max(0, Math.min(approvals.length - 1, index + step))];
}

function focusItem(id: string): void {
  requestAnimationFrame(() =>
    document
      .querySelector<HTMLElement>(`[data-approval-item="${id}"]`)
      ?.focus(),
  );
}

export function useApprovalShortcuts({
  approvals,
  selected,
  current,
  waiting,
  select,
  decide,
}: ShortcutInputs): Shortcuts {
  const [armed, setArmed] = useState<Arm | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const disarm = useCallback(() => setArmed(null), []);

  function move(event: KeyboardEvent): void {
    const inList =
      event.target instanceof HTMLElement &&
      event.target.hasAttribute("data-approval-item");
    const down = event.key === "j" || (inList && event.key === "ArrowDown");
    const up = event.key === "k" || (inList && event.key === "ArrowUp");
    if (!down && !up) return;
    const next = neighbour(approvals, selected, down ? 1 : -1);
    if (next === undefined) return;
    event.preventDefault();
    select(next.id);
    setArmed(null);
    if (inList) focusItem(next.id);
  }

  function shortcut(event: KeyboardEvent): void {
    const decision = chord(event);
    if (decision === null || current === null || !waiting) return;
    event.preventDefault();
    const next = press(armed, {
      decision,
      approvalId: current.id,
      truncated: current.arguments_truncated,
      repeat: event.repeat,
      now: Date.now(),
    });
    if (next.kind === "ignore") return;
    if (next.kind === "too_large") {
      setAnnouncement(TOO_LARGE);
    } else if (next.kind === "decide") {
      setArmed(null);
      setAnnouncement("");
      decide(current, next.decision);
    } else {
      setArmed(next.arm);
      setAnnouncement(armedText(decision, current));
    }
  }

  const onKey = useEffectEvent((event: KeyboardEvent) => {
    if (typing(event.target)) return;
    if (!event.metaKey && !event.ctrlKey && !event.altKey) move(event);
    else shortcut(event);
  });

  useEffect(() => {
    const listener = (event: KeyboardEvent) => onKey(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  // An arm lapses after 2 s, and the live region says nothing was decided.
  useEffect(() => {
    if (armed === null) return;
    const timer = setTimeout(
      () => {
        setArmed(null);
        setAnnouncement(NOTHING_DECIDED);
      },
      Math.max(0, armed.until - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [armed]);

  return { announcement, disarm };
}
