import type { ReactNode } from "react";

import { markdownBlocks, type InlinePart } from "@/lib/approval-fields";

function inline(parts: InlinePart[]): ReactNode[] {
  return parts.map((part, index) => {
    if (part.kind === "code")
      return (
        <code key={index} className="font-mono text-ui">
          {part.text}
        </code>
      );
    if (part.kind === "strong") return <strong key={index}>{part.text}</strong>;
    return part.text;
  });
}

/**
 * A small Markdown reader for a request's text field. It builds React text nodes only, so nothing is
 * injected as HTML (WTAP-01).
 */
export function MarkdownText({ text }: { text: string }) {
  return (
    <>
      {markdownBlocks(text).map((block, index) =>
        block.kind === "list" ? (
          <ul key={index} className="list-disc space-y-1 pl-5">
            {block.items.map((item, line) => (
              <li key={line}>{inline(item)}</li>
            ))}
          </ul>
        ) : (
          <p key={index} className="mb-2 last:mb-0">
            {block.lines.map((parts, line) => (
              <span key={line}>
                {line > 0 ? <br /> : null}
                {inline(parts)}
              </span>
            ))}
          </p>
        ),
      )}
    </>
  );
}
