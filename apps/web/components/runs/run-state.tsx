import type { RunStatus } from "@autobots/api-client";
import type { ComponentProps } from "react";

import { Badge } from "@/components/ui/badge";
import { StatusDot, type StatusDotTone } from "@/components/ui/status-dot";
import { RUN_STATUS_LABEL, runTone, type RunTone } from "@/lib/runs/status";
import { cn } from "@/lib/utils";

// Decision 0021 R3–R4: a run state's dot or badge repeats its words in its tone, never replaces them.
// The tones come from lib/runs/status.ts (R-37), so every screen colors a state alike.
const TONE_TEXT: Readonly<Record<RunTone, string>> = {
  live: "text-live-text",
  attention: "text-attention",
  success: "text-foreground",
  failure: "text-destructive",
  idle: "text-foreground",
};

const TONE_DOT: Readonly<Record<RunTone, StatusDotTone>> = {
  live: "live",
  attention: "attention",
  success: "success",
  failure: "danger",
  idle: "idle",
};

const TONE_BADGE: Readonly<
  Record<RunTone, ComponentProps<typeof Badge>["variant"]>
> = {
  live: "live",
  attention: "attention",
  success: "success",
  failure: "danger",
  idle: "muted",
};

/** The state's dot and words, for a run list row, the run panel and the workflow monitor. */
export function StateLine({
  status,
  text,
}: {
  status: RunStatus;
  /** Words that add to the state's own, such as its progress. */
  text?: string;
}) {
  const tone = runTone(status);
  return (
    <span
      data-field="state"
      className={cn("inline-flex items-center gap-2 text-ui", TONE_TEXT[tone])}
    >
      <StatusDot tone={TONE_DOT[tone]} size="md" />
      {text ?? RUN_STATUS_LABEL[status]}
    </span>
  );
}

/** The run page header's badge. The status sentence says the same to assistive technology. */
export function RunStateBadge({ status }: { status: RunStatus }) {
  return (
    <Badge aria-hidden="true" variant={TONE_BADGE[runTone(status)]} dot>
      {RUN_STATUS_LABEL[status]}
    </Badge>
  );
}
