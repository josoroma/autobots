import { Section } from "@/components/runs/workspace/section";
import type { StoredResult } from "@/components/runs/workspace/use-published-result";
import type { LiveText } from "@/lib/runs/run-events";

const RESULT_TEXT =
  "font-document max-h-[60vh] overflow-auto text-[15px] leading-relaxed break-words whitespace-pre-wrap";

/** The stored result, or the result while it's written (US-15.24). The stored one replaces it. */
export function ResultSection({
  result,
  live,
}: {
  result: StoredResult | null;
  live: LiveText | null;
}) {
  if (result === null && live === null) return null;
  return (
    <Section id="result-heading" title="Result">
      {result !== null ? (
        <div className="space-y-1.5">
          <p className="text-muted-foreground text-[12.5px]">
            {result.name}, as stored.
          </p>
          <pre
            data-field="result-text"
            className={RESULT_TEXT}
            tabIndex={0}
            role="region"
            aria-label={`Result ${result.name}`}
          >
            {result.text}
          </pre>
        </div>
      ) : live !== null ? (
        <div className="space-y-1.5">
          <p
            data-field="live-note"
            className="text-muted-foreground text-[12.5px]"
          >
            {live.joined
              ? "Being written. Joined partway; the stored result replaces this."
              : "Being written. The stored result replaces this when it's saved."}
          </p>
          <pre
            data-field="live-result"
            className={RESULT_TEXT}
            tabIndex={0}
            role="region"
            aria-label="Result being written"
          >
            {live.text}
          </pre>
        </div>
      ) : null}
    </Section>
  );
}
