"use client";

import { getRunWorkspace } from "@autobots/api-client";
import { CircleAlert, RotateCw } from "lucide-react";
import Link from "next/link";

import {
  PanelFacts,
  PanelPlan,
  PanelSummary,
} from "@/components/runs/panel/panel-parts";
import {
  STALE,
  usePanelCommands,
} from "@/components/runs/panel/use-panel-commands";
import { RunCommandButtons } from "@/components/runs/run-command-buttons";
import { Button, buttonVariants } from "@/components/ui/button";
import { readOf } from "@/lib/load";
import { useResource, type ResourceState } from "@/lib/use-resource";

// PRD-Studio RN-04: one run's progress and controls, under the list so Tab never climbs back up.
export function RunPanel({
  runId,
  onChanged,
}: {
  runId: string;
  onChanged: () => void;
}) {
  const { state, reload } = useResource(readOf(getRunWorkspace, runId));
  const commands = usePanelCommands(runId, () => {
    reload();
    onChanged();
  });
  if (state.kind !== "ready") return <PanelUnread state={state} />;
  const view = state.value;
  const run = view.run;
  return (
    <section
      id="run-panel"
      aria-labelledby="run-panel-heading"
      data-panel={run.id}
      data-version={run.version}
      className="space-y-5 rounded-xl border p-5"
    >
      <PanelSummary view={view} />
      <PanelPlan tasks={view.plan?.tasks ?? []} />
      <PanelFacts view={view} />
      <div className="flex flex-wrap items-center gap-2">
        <Link
          href={`/runs/${encodeURIComponent(run.id)}`}
          className={buttonVariants({ variant: "outline" })}
        >
          Open run
        </Link>
        <RunCommandButtons
          commands={view.allowed_commands}
          busy={commands.busy}
          onSend={(command) => void commands.send(command, run.version)}
        />
      </div>
      <PanelRefusal
        refusal={commands.refusal}
        onReload={() => {
          commands.clear();
          reload();
        }}
      />
    </section>
  );
}

// Loading, or unavailable for any reason: the panel names no cause, and the run page has the detail.
function PanelUnread({ state }: { state: ResourceState<unknown> }) {
  return state.kind === "loading" || state.kind === "idle" ? (
    <p role="status" className="text-muted-foreground text-sm">
      Loading the run&apos;s details.
    </p>
  ) : (
    <p role="alert" className="text-sm">
      This run&apos;s details are unavailable.
    </p>
  );
}

function PanelRefusal({
  refusal,
  onReload,
}: {
  refusal: string | null;
  onReload: () => void;
}) {
  if (refusal === null) return null;
  return (
    <div
      role="alert"
      data-panel-refusal="true"
      className="flex flex-wrap items-start gap-2 text-sm"
    >
      <CircleAlert
        aria-hidden="true"
        className="text-destructive mt-0.5 size-4 shrink-0"
      />
      <span className="min-w-0 flex-1">{refusal}</span>
      {refusal === STALE ? (
        <Button variant="outline" size="sm" onClick={onReload}>
          <RotateCw aria-hidden="true" />
          Reload the panel
        </Button>
      ) : null}
    </div>
  );
}
