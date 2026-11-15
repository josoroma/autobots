import type { WorkflowExecutionList, WorkflowView } from "@autobots/api-client";
import { useEffect, useRef } from "react";

import { LoadState } from "@/components/ui/load-state";
import { Select } from "@/components/ui/field";
import { PreviewSteps } from "@/components/workflows/preview-steps";
import { RecentExecutions } from "@/components/workflows/recent-executions";
import { useWorkflowPreview } from "@/components/workflows/use-workflow-preview";
import type { Resource } from "@/lib/use-resource";

/** Which published version, or the draft, the preview shows; the choice is kept in the URL. */
function VersionSwitch({
  workflow,
  shown,
  onChoose,
}: {
  workflow: WorkflowView;
  shown: string;
  onChoose: (version: string) => void;
}) {
  return (
    <label className="ml-auto flex items-center gap-2 text-[13px]">
      <span className="text-muted-foreground">Version</span>
      <Select
        value={shown}
        onChange={(event) => onChoose(event.target.value)}
        className="h-8 w-40"
      >
        {[...workflow.versions].reverse().map((item) => (
          <option key={item.version} value={String(item.version)}>
            Version {item.version}
          </option>
        ))}
        {workflow.draft === null ? null : <option value="draft">Draft</option>}
      </Select>
    </label>
  );
}

/**
 * The chosen workflow's preview and recent executions (PRD-Studio WF-03, WF-04). It sits under the
 * list, so Tab never climbs.
 */
export function WorkflowPreview({
  workflow,
  version,
  executions,
  onChooseVersion,
  now,
}: {
  workflow: WorkflowView;
  /** The version asked for in the URL, or null for its default. */
  version: string | null;
  /** The workflow's recent executions, read since it was chosen. */
  executions: Resource<WorkflowExecutionList>;
  onChooseVersion: (version: string) => void;
  /** When the list was read, in epoch milliseconds. */
  now: number;
}) {
  const read = useWorkflowPreview(workflow, version, executions);
  const heading = useRef<HTMLHeadingElement>(null);

  // The preview sits under the list, often below the fold, and the Preview link doesn't scroll.
  // So choosing a workflow brings its preview into view and moves focus to its heading, which
  // also tells a screen reader where it went. Changing the version keeps the place.
  useEffect(() => {
    const target = heading.current;
    if (target === null) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.focus({ preventScroll: true });
    target.scrollIntoView({
      block: "start",
      behavior: still ? "auto" : "smooth",
    });
  }, [workflow.id]);

  return (
    <section
      aria-labelledby="preview-heading"
      data-panel={workflow.id}
      className="space-y-5 rounded-xl border p-5"
    >
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <h2
          id="preview-heading"
          ref={heading}
          tabIndex={-1}
          className="scroll-mt-4 text-[15px] font-semibold outline-none"
        >
          Preview: {workflow.name}
        </h2>
        {read.shown === null ? null : (
          <VersionSwitch
            workflow={workflow}
            shown={read.shown}
            onChoose={onChooseVersion}
          />
        )}
      </div>
      {read.shown === null ? (
        <p className="text-muted-foreground text-sm">
          Nothing is published or drafted yet.
        </p>
      ) : read.steps === null ? (
        <LoadState
          state={read.stepsState}
          what="its steps"
          onRetry={read.retrySteps}
          pending={read.stepsPending}
        />
      ) : (
        <PreviewSteps steps={read.steps} />
      )}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Recent executions</h3>
        {read.executions === null ? (
          <LoadState
            state={read.executionsState}
            what="recent executions"
            onRetry={read.retryExecutions}
            pending={read.executionsPending}
          />
        ) : (
          <RecentExecutions executions={read.executions.executions} now={now} />
        )}
      </div>
    </section>
  );
}
