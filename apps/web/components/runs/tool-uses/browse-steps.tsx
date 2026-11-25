"use client";

import { listBrowseSteps, type BrowseStep } from "@autobots/api-client";
import { useEffect, useState } from "react";

import { LoadState } from "@/components/ui/load-state";
import { load, readOf, type LoadFailure } from "@/lib/load";
import {
  screenshotAlt,
  screenshotUrl,
  stepsLabel,
  stepTitle,
  touchText,
} from "@/lib/runs/browse-steps";

// Decision 0035 Y11: with no approval under YOLO, this is how a person sees afterwards what a
// browse on browser-use did. Read only when opened.

export function BrowseSteps({
  runId,
  useId,
  count,
}: {
  runId: string;
  useId: number;
  count: number;
}) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="mt-1.5 font-sans"
      data-browse-steps={useId}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer text-xs font-medium underline underline-offset-2">
        {stepsLabel(count)}
      </summary>
      {open ? <StepList runId={runId} useId={useId} /> : null}
    </details>
  );
}

function StepList({ runId, useId }: { runId: string; useId: number }) {
  const [request, setRequest] = useState(0);
  const [state, setState] = useState<{
    steps: BrowseStep[] | null;
    failure: LoadFailure | null;
  }>({ steps: null, failure: null });
  useEffect(() => {
    const controller = new AbortController();
    void load(readOf(listBrowseSteps, runId, String(useId)), {
      signal: controller.signal,
    }).then((loaded) => {
      if (controller.signal.aborted) return;
      setState(
        loaded.kind === "ready"
          ? { steps: loaded.value.steps, failure: null }
          : { steps: null, failure: loaded },
      );
    });
    return () => controller.abort();
  }, [runId, useId, request]);
  if (state.steps === null) {
    return (
      <LoadState
        state={state.failure ?? { kind: "loading" }}
        what="steps"
        onRetry={() => setRequest((count) => count + 1)}
        pending={state.failure === null}
      />
    );
  }
  if (state.steps.length === 0) {
    return (
      <p className="text-muted-foreground mt-1 text-xs">No steps were kept.</p>
    );
  }
  return (
    <ol className="mt-2 space-y-3" aria-label="Browse steps">
      {state.steps.map((step) => (
        <li key={step.step} data-browse-step={step.step}>
          <p className="text-xs">{stepTitle(step)}</p>
          {step.touched.length === 0 ? null : (
            <ul className="text-muted-foreground text-xs wrap-anywhere">
              {step.touched.map((touch, index) => (
                <li key={`${index}-${touch.kind}`}>{touchText(touch)}</li>
              ))}
            </ul>
          )}
          {step.submits.length === 0 ? null : (
            <ul className="text-muted-foreground text-xs">
              {step.submits.map((submit, index) => (
                <li key={`${index}-${submit}`}>Submitted to {submit}</li>
              ))}
            </ul>
          )}
          {step.screenshot ? (
            // eslint-disable-next-line @next/next/no-img-element -- a private, authorized image the BFF serves; next/image can't proxy it
            <img
              src={screenshotUrl(runId, useId, step.step)}
              alt={screenshotAlt(step)}
              loading="lazy"
              className="border-border mt-1 w-full max-w-72 rounded border"
            />
          ) : (
            <p className="text-muted-foreground text-xs">
              No screenshot was kept.
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
