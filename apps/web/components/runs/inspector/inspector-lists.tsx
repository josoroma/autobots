import type { RunInspector } from "@autobots/api-client";

import { HairlineSection } from "@/components/ui/section";

/** What each tool operation did. Its arguments and result stay out of this view. */
export function ToolAttempts({
  attempts,
}: {
  attempts: RunInspector["tool_attempts"];
}) {
  return (
    <HairlineSection
      id="tools-heading"
      title="Tool operation attempts"
      note="This run only. A child run shows its own."
    >
      {attempts.length === 0 ? (
        <p className="text-muted-foreground text-sm">No tool operations.</p>
      ) : (
        <ul className="divide-y border-y text-sm">
          {attempts.map((attempt) => (
            <li
              key={attempt.operation_id}
              data-tool={attempt.tool_id}
              data-tool-status={attempt.status}
              className="py-2 break-words"
            >
              <code className="font-mono text-ui font-medium break-all">
                {attempt.tool_id}
              </code>
              <span className="text-muted-foreground">
                , version {attempt.tool_version}:{" "}
              </span>
              {attempt.status}
              {attempt.failure_code === null
                ? ""
                : ` (${attempt.failure_code})`}
            </li>
          ))}
        </ul>
      )}
    </HairlineSection>
  );
}

/** What completed tasks cited. An artifact it names links to its download. */
export function Evidence({ items }: { items: RunInspector["evidence"] }) {
  return (
    <HairlineSection id="evidence-heading" title="Evidence">
      {items.length === 0 ? (
        <p data-field="evidence" className="text-muted-foreground text-sm">
          No task has cited evidence.
        </p>
      ) : (
        <ul data-field="evidence" className="divide-y border-y text-sm">
          {items.map((item) => (
            <li
              key={`${item.task_id}-${item.reference}`}
              className="space-y-1 py-3 break-words"
            >
              <p>
                <span className="text-muted-foreground">
                  Task{" "}
                  <span className="font-mono text-xs break-all">
                    {item.task_id}
                  </span>
                  :
                </span>{" "}
                <span className="font-document text-lead leading-relaxed">
                  {item.summary}
                </span>
              </p>
              <p className="font-mono text-xs break-all">
                {item.kind === "artifact" && item.artifact_id !== null ? (
                  <a
                    href={`/api/v1/artifacts/${item.artifact_id}/download`}
                    className="font-medium underline underline-offset-4"
                  >
                    {item.reference}
                  </a>
                ) : (
                  <span className="text-muted-foreground">
                    {`${item.kind}: ${item.reference}`}
                  </span>
                )}
              </p>
            </li>
          ))}
        </ul>
      )}
    </HairlineSection>
  );
}

/** That checkpoints exist, and where. Never what they hold. */
export function Checkpoints({ view }: { view: RunInspector }) {
  return (
    <HairlineSection id="checkpoints-heading" title="Checkpoints">
      {view.checkpoints.length === 0 ? (
        <p className="text-muted-foreground text-sm">No checkpoints.</p>
      ) : (
        <ol className="divide-y border-y text-sm">
          {view.checkpoints.map((checkpoint) => (
            <li
              key={checkpoint.checkpoint_id}
              data-checkpoint={checkpoint.checkpoint_id}
              className="py-2 break-all"
            >
              Step {checkpoint.step ?? "not recorded"},{" "}
              {checkpoint.source ?? "unknown source"}:{" "}
              <span className="text-muted-foreground font-mono text-xs">
                {checkpoint.checkpoint_id}
              </span>
            </li>
          ))}
        </ol>
      )}
      {view.checkpoints_truncated ? (
        <p className="text-muted-foreground text-sm">
          Showing the first {view.checkpoints.length} checkpoints.
        </p>
      ) : null}
    </HairlineSection>
  );
}
