import type { ApprovalView } from "@autobots/api-client";
import { useState } from "react";

import { MarkdownText } from "@/components/approvals/markdown-text";
import { parsedFields, readsAsMarkdown } from "@/lib/approval-fields";
import { cn } from "@/lib/utils";

const VIEWS = [
  ["fields", "Fields"],
  ["json", "JSON"],
] as const;

type View = (typeof VIEWS)[number][0];

// Each field in the stored order. A text field with Markdown is also shown rendered, as text nodes.
function RequestFields({ fields }: { fields: [string, unknown][] }) {
  return (
    <dl data-approval-fields="true" className="border-t text-[13.5px]">
      {fields.map(([key, value]) => (
        <div
          key={key}
          className="grid gap-1 border-b px-3.5 py-2.5 last:border-b-0 sm:grid-cols-[8rem_minmax(0,1fr)]"
        >
          <dt className="text-muted-foreground font-mono text-[12.5px]">
            {key}
          </dt>
          <dd className="min-w-0 space-y-2">
            {typeof value === "string" ? (
              <>
                <pre className="font-mono text-[13px] break-words whitespace-pre-wrap">
                  {value}
                </pre>
                {readsAsMarkdown(value) ? (
                  <div
                    data-approval-rendered="true"
                    className="rounded-md border px-3 py-2 font-serif text-[15px] leading-relaxed"
                  >
                    <span className="sr-only">Rendered: </span>
                    <MarkdownText text={value} />
                  </div>
                ) : null}
              </>
            ) : (
              <pre className="font-mono text-[13px] break-words whitespace-pre-wrap">
                {JSON.stringify(value, null, 2)}
              </pre>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * The exact request the decision binds, by its hash and size, with its target and effect. It shows
 * whole as JSON, or as Fields when the stored order can be kept (PRD-Studio AP-03).
 */
export function ExactRequest({ approval }: { approval: ApprovalView }) {
  const [view, setView] = useState<View>("json");
  const fields = parsedFields(approval);
  return (
    <div className="overflow-hidden rounded-xl border">
      <div className="flex flex-wrap items-center gap-2 border-b px-3.5 py-2 text-[12.5px] dark:bg-muted/40">
        <span className="font-semibold">Exact request</span>
        <span
          data-approval-digest="true"
          className="text-muted-foreground font-mono"
        >
          sha256 {approval.argument_hash.slice(0, 8)}…
          {approval.argument_hash.slice(-4)} ·{" "}
          {approval.arguments_bytes.toLocaleString()} bytes
        </span>
        <span className="flex-1" />
        <div role="group" aria-label="Request view" className="flex gap-1">
          {VIEWS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={view === id}
              disabled={id === "fields" && fields === null}
              onClick={() => setView(id)}
              className={cn(
                "rounded-md border border-transparent px-2 py-0.5 disabled:opacity-60",
                view === id && "border-border bg-background dark:bg-accent",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <dl className="grid grid-cols-[6.5rem_minmax(0,1fr)] text-[13.5px]">
        <div data-approval-target="true" className="contents">
          <dt className="text-muted-foreground border-b px-3.5 py-2.5 font-mono text-[12.5px]">
            Target<span className="sr-only">:</span>
          </dt>{" "}
          <dd className="border-b py-2.5 pr-3.5 break-words">
            {approval.resource_target ??
              "not recorded. Read the exact request below."}
          </dd>
        </div>
        <div className="contents">
          <dt className="text-muted-foreground px-3.5 py-2.5 font-mono text-[12.5px]">
            Effect<span className="sr-only">:</span>
          </dt>{" "}
          <dd className="py-2.5 pr-3.5">
            {approval.operation_class.replaceAll("_", " ")}
          </dd>
        </div>
      </dl>
      {view === "fields" && fields !== null ? (
        <RequestFields fields={fields} />
      ) : (
        <pre
          tabIndex={0}
          className="max-h-96 overflow-auto border-t p-3.5 font-mono text-[13px] leading-relaxed break-words whitespace-pre-wrap dark:bg-muted/30"
        >
          {approval.arguments}
        </pre>
      )}
    </div>
  );
}
