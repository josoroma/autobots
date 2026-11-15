/**
 * A filter control's value, shown at once and written to the URL after `delayMs` (XWEB-13, WTAP-15).
 * The rules are in `url-draft.ts`; this keeps them in React state. `write` is called with the value
 * as `normalize` makes it, such as a search trimmed, and only when the URL doesn't hold it already.
 */
import { useEffect, useEffectEvent, useState } from "react";

import {
  followUrl,
  pendingWrite,
  startDraft,
  typed,
  wrote,
} from "@/lib/url-draft";

export interface UrlDraftOptions {
  /** How long a change waits before it's written, so typing in a search writes once. */
  delayMs?: number;
  /** The form the URL keeps, such as a search without its spaces at either end. */
  normalize?: (raw: string) => string;
}

export interface UrlDraftControl {
  /** What the control shows. */
  value: string;
  /** The person changed the control. */
  change: (next: string) => void;
}

const AS_TYPED = (raw: string): string => raw;

export function useUrlDraft(
  value: string,
  write: (next: string) => void,
  { delayMs = 0, normalize = AS_TYPED }: UrlDraftOptions = {},
): UrlDraftControl {
  const [kept, setKept] = useState(() => startDraft(value));
  const state = followUrl(kept, value);
  if (state !== kept) setKept(state);
  const next = pendingWrite(state, normalize);
  const send = useEffectEvent((written: string) => {
    setKept((current) => wrote(current, written));
    write(written);
  });
  useEffect(() => {
    if (next === null) return;
    const timer = setTimeout(() => send(next), delayMs);
    return () => clearTimeout(timer);
  }, [next, delayMs]);
  return {
    value: state.draft,
    change: (draft) => setKept((current) => typed(current, draft)),
  };
}
