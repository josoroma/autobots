/**
 * A list filter that shows what a person chose or typed at once and keeps the URL in step, so a
 * reload, Back and a shared link keep it (XWEB-13, PRD-Tool-Catalog TS-01, PRD-Studio WF-01). The
 * URL's value coming back from the filter's own write keeps the box as it is, even with typing done
 * since; any other change to the URL, such as Back or a link to the bare list, replaces what the box
 * shows (WTAP-15). Pure and JSX-free, so `node --test` covers it; `use-url-draft.ts` drives it.
 */

export interface UrlDraft {
  /** What the control shows. */
  readonly draft: string;
  /** The URL's value the draft last followed. */
  readonly followed: string;
  /** Values written since then, oldest first, whose return hasn't been seen. */
  readonly sent: readonly string[];
}

// Enough to cover the writes a fast typist sends before the first comes back.
const KEPT_WRITES = 16;

/** A draft showing the URL's value. */
export function startDraft(value: string): UrlDraft {
  return { draft: value, followed: value, sent: [] };
}

/**
 * The URL holds `value` now. A value this draft wrote comes back without changing the box, and the
 * writes before it are forgotten, as a newer write replaced them. Any other value replaces the box.
 */
export function followUrl(state: UrlDraft, value: string): UrlDraft {
  if (value === state.followed) return state;
  const own = state.sent.indexOf(value);
  if (own < 0) return startDraft(value);
  return { ...state, followed: value, sent: state.sent.slice(own + 1) };
}

/** The person changed the control. */
export function typed(state: UrlDraft, draft: string): UrlDraft {
  return { ...state, draft };
}

/** The URL was asked to hold `value`. */
export function wrote(state: UrlDraft, value: string): UrlDraft {
  return { ...state, sent: [...state.sent, value].slice(-KEPT_WRITES) };
}

/**
 * The value to write now, as `normalize` makes it, or null when the URL holds it already or a write
 * of it is on its way.
 */
export function pendingWrite(
  state: UrlDraft,
  normalize: (raw: string) => string,
): string | null {
  const next = normalize(state.draft);
  return next === state.followed || state.sent.includes(next) ? null : next;
}
