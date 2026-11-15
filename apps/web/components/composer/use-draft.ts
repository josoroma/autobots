/**
 * The goal's draft, which survives setup in this tab only; the profile, Expert and budget choices
 * are plain state (WCMP-18). Restoring the draft never starts anything: the one admission happens
 * only when Run is pressed. No credential is ever kept here.
 */
import { useState, useSyncExternalStore } from "react";

const DRAFT_KEY = "autobots.draft";

// The draft is read once, so nothing needs to follow storage changes from other tabs.
const subscribe = () => () => undefined;

function storedDraft(): string {
  try {
    return window.sessionStorage.getItem(DRAFT_KEY) ?? "";
  } catch {
    return "";
  }
}

export interface Draft {
  text: string;
  edit: (text: string) => void;
}

export function useDraft(): Draft {
  // Storage is read only in the browser, so the server render and hydration agree on an empty goal.
  const restored = useSyncExternalStore(subscribe, storedDraft, () => "");
  const [edited, setEdited] = useState<string | null>(null);

  function edit(text: string): void {
    setEdited(text);
    try {
      window.sessionStorage.setItem(DRAFT_KEY, text);
    } catch {
      // Storage is unavailable, so the draft lasts only as long as this page.
    }
  }

  return { text: edited ?? restored, edit };
}
