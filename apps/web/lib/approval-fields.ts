/**
 * How an approval's exact request is read for its Fields view (WTAP-01, WTAP-09). Fields keep the
 * stored order, and a text field's Markdown is read into text parts only, so the screen builds
 * text nodes and nothing is injected as HTML. Pure and JSX-free, so `node --test` covers it.
 */
import type { ApprovalView } from "@autobots/api-client";

// JSON.parse lists integer-like keys first, in numeric order, whatever order they were stored in.
const INTEGER_KEY = /^\d+$/;
const LIST_ITEM = /^\s*[-*] /;
const MARKDOWN = /\n|`|\*\*|^\s*[-*] /m;

/**
 * The request's top-level fields in their stored order, or null when it has no Fields view: it
 * isn't shown whole, isn't one JSON object, or has a key JSON would reorder (PRD-Studio AP-03).
 */
export function parsedFields(
  approval: Pick<ApprovalView, "arguments" | "arguments_truncated">,
): [string, unknown][] | null {
  if (approval.arguments_truncated) return null;
  let value: unknown;
  try {
    value = JSON.parse(approval.arguments);
  } catch {
    return null;
  }
  if (value === null || typeof value !== "object" || Array.isArray(value))
    return null;
  const entries: [string, unknown][] = Object.entries(value);
  return entries.some(([key]) => INTEGER_KEY.test(key)) ? null : entries;
}

/** A text field is also shown rendered when it has a line break, code, bold or a list item. */
export function readsAsMarkdown(text: string): boolean {
  return MARKDOWN.test(text);
}

/** One run of a line: plain text, inline code or bold. */
export interface InlinePart {
  kind: "text" | "code" | "strong";
  text: string;
}

/** A paragraph, one entry per line, or a list, one entry per item. */
export type MarkdownBlock =
  | { kind: "paragraph"; lines: InlinePart[][] }
  | { kind: "list"; items: InlinePart[][] };

/** A line's inline code and bold, with an unclosed or empty marker kept as typed. */
export function inlineParts(line: string): InlinePart[] {
  return line
    .split(/(`[^`]+`|\*\*[^*]+\*\*)/)
    .filter((part) => part !== "")
    .map((part) => {
      if (part.length > 1 && part.startsWith("`") && part.endsWith("`"))
        return { kind: "code", text: part.slice(1, -1) };
      if (part.length > 3 && part.startsWith("**") && part.endsWith("**"))
        return { kind: "strong", text: part.slice(2, -2) };
      return { kind: "text", text: part };
    });
}

/** Blocks split at blank lines. A block whose every line is a `-` or `*` item is a list. */
export function markdownBlocks(text: string): MarkdownBlock[] {
  return text.split(/\n{2,}/).map((block) => {
    const lines = block.split("\n");
    return lines.every((line) => LIST_ITEM.test(line))
      ? {
          kind: "list",
          items: lines.map((line) => inlineParts(line.replace(LIST_ITEM, ""))),
        }
      : { kind: "paragraph", lines: lines.map(inlineParts) };
  });
}
