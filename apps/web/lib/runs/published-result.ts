/**
 * The stored result the run page shows: the newest published artifact's text (US-15.24). The
 * stored artifact replaces any live text, so this reads only text, and a reply that can't be shown
 * leaves the page as it is. Runs in the browser and under `node --test`.
 */

export interface ReadOptions {
  /** Aborts a read that a newer artifact replaced (WRUN-16). */
  signal?: AbortSignal;
  /** For tests. The browser's own fetch otherwise. */
  fetch?: typeof globalThis.fetch;
}

/** The artifact's text, or null when it isn't text, is refused, or can't be read. */
export async function readStoredText(
  artifactId: string,
  options: ReadOptions = {},
): Promise<string | null> {
  // Called without a receiver, so the browser's fetch keeps its own.
  const fetch = options.fetch ?? globalThis.fetch;
  try {
    const reply = await fetch(
      `/api/v1/artifacts/${encodeURIComponent(artifactId)}/download`,
      {
        cache: "no-store",
        ...(options.signal === undefined ? {} : { signal: options.signal }),
      },
    );
    if (!reply.ok) return null;
    const type = reply.headers.get("content-type") ?? "";
    if (!type.startsWith("text/") && !type.startsWith("application/json"))
      return null;
    return await reply.text();
  } catch {
    return null;
  }
}
