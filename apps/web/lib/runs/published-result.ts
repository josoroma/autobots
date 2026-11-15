/**
 * The stored result the run page shows: the newest published artifact's text (US-15.24). The
 * stored artifact replaces any live text, so this reads only text, and a reply that can't be shown
 * leaves the page as it is. Runs in the browser and under `node --test`.
 */
import { downloadArtifact, type ReadOptions } from "../api/browser.ts";

/** The artifact's text, or null when it isn't text, is refused, or can't be read. */
export async function readStoredText(
  artifactId: string,
  options: ReadOptions = {},
): Promise<string | null> {
  try {
    const reply = await downloadArtifact(artifactId, options);
    if (!reply.ok) return null;
    const type = reply.headers.get("content-type") ?? "";
    if (!type.startsWith("text/") && !type.startsWith("application/json"))
      return null;
    return await reply.text();
  } catch {
    return null;
  }
}
