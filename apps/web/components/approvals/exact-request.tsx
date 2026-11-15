import type { ApprovalView } from "@autobots/api-client";
import { useState } from "react";

import { MarkdownText } from "@/components/approvals/markdown-text";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { parsedFields, readsAsMarkdown } from "@/lib/approval-fields";

const VIEWS = [
  ["fields", "Fields"],
  ["json", "JSON"],
] as const;

type View = (typeof VIEWS)[number][0];

// Each field in the stored order. A text field with Markdown is also shown rendered, as text nodes.
function RequestFields({ fields }: { fields: [string, unknown][] }) {
  return (
    <dl data-approval-fields="true" className="border-t text-body">
      {fields.map(([key, value]) => (
        <div
          key={key}
          className="grid gap-1 border-b px-3.5 py-2.5 last:border-b-0 sm:grid-cols-[8rem_minmax(0,1fr)]"
        >
          <dt className="text-muted-foreground font-mono text-meta">{key}</dt>
          <dd className="min-w-0 space-y-2">
            {typeof value === "string" ? (
              <>
                <pre className="font-mono text-ui break-words whitespace-pre-wrap">
                  {value}
                </pre>
                {readsAsMarkdown(value) ? (
                  <div
                    data-approval-rendered="true"
                    className="rounded-md border px-3 py-2 font-serif text-lead leading-relaxed"
                  >
                    <span className="sr-only">Rendered: </span>
                    <MarkdownText text={value} />
                  </div>
                ) : null}
              </>
            ) : (
              <pre className="font-mono text-ui break-words whitespace-pre-wrap">
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
      <div className="flex flex-wrap items-center gap-2 border-b px-3.5 py-2 text-meta dark:bg-muted/40">
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
        <SegmentedControl
          label="Request view"
          size="compact"
          items={VIEWS.map(([id, label]) => ({
            id,
            label,
            disabled: id === "fields" && fields === null,
          }))}
          value={view}
          onChange={setView}
        />
      </div>
      <dl className="grid grid-cols-[6.5rem_minmax(0,1fr)] text-body">
        <div data-approval-target="true" className="contents">
          <dt className="text-muted-foreground border-b px-3.5 py-2.5 font-mono text-meta">
            Target<span className="sr-only">:</span>
          </dt>{" "}
          <dd className="border-b py-2.5 pr-3.5 break-words">
            {approval.resource_target ??
              "not recorded. Read the exact request below."}
          </dd>
        </div>
        <div className="contents">
          <dt className="text-muted-foreground px-3.5 py-2.5 font-mono text-meta">
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
          className="max-h-96 overflow-auto border-t p-3.5 font-mono text-ui leading-relaxed break-words whitespace-pre-wrap dark:bg-muted/30"
        >
          {approval.arguments}
        </pre>
      )}
    </div>
  );
}
