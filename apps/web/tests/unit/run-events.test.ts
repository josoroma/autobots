/**
 * What the run page derives from its stored events (R-49, WRUN-15): the timeline's words for every
 * payload type, merging replays by sequence, live text, the newest published result and the
 * tool-event count that tells the Tools used section to read again.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { parseRunEvent, type RunEvent } from "@autobots/api-client";

import {
  describeEvent,
  latestPublished,
  mergeEvents,
  toolEventCount,
  toTimeline,
  withDelta,
} from "../../lib/runs/run-events.ts";

const RUN = "11111111-1111-4111-8111-111111111111";
const ARTIFACT = "33333333-3333-4333-8333-333333333333";
const APPROVAL = "44444444-4444-4444-8444-444444444444";

function event(sequence: number, payload: Record<string, unknown>): RunEvent {
  return parseRunEvent({
    schema_version: 1,
    run_id: RUN,
    sequence,
    causal_ids: [],
    occurred_at: "2026-11-15T00:00:00+00:00",
    payload,
  });
}

const status = (sequence: number, previous: string, current: string) =>
  event(sequence, { type: "run.status_changed", previous, current });
const published = (sequence: number, name: string, id = ARTIFACT) =>
  event(sequence, {
    type: "artifact.published",
    artifact_id: id,
    name,
    sha256: "a".repeat(64),
  });
const started = (sequence: number) =>
  event(sequence, {
    type: "tool.use.started",
    tool_id: "web_search",
    tool_use_id: sequence,
    tool_version: 1,
    group: null,
    task_id: null,
  });
const completed = (
  sequence: number,
  outcome: string,
  code: string | null = null,
) =>
  event(sequence, {
    type: "tool.use.completed",
    tool_id: "web_search",
    tool_use_id: sequence,
    tool_version: 1,
    outcome,
    code,
    duration_ms: 5,
    operation_id: null,
  });

test("every payload type reads as its own timeline line", () => {
  const lines = [
    status(1, "queued", "running"),
    status(2, "running", "running"),
    event(3, {
      type: "effect.reconciled",
      operation_id: "op-1",
      outcome: "not_delivered",
    }),
    event(4, {
      type: "approval.requested",
      approval_id: APPROVAL,
      tool_id: "github_issue",
    }),
    event(5, {
      type: "approval.decided",
      approval_id: APPROVAL,
      decision: "approved",
    }),
    started(6),
    completed(7, "failed", "rate_limited"),
    completed(8, "succeeded"),
    event(9, {
      type: "result.text.delta",
      segment: 1,
      offset: 0,
      text: "Hi",
    }),
    published(10, "report.md"),
    event(11, {
      type: "artifact.missing",
      artifact_id: ARTIFACT,
      name: "report.md",
    }),
  ].map(describeEvent);
  assert.deepEqual(lines, [
    "Run moved from queued to running",
    "Run running",
    "An unknown effect was reconciled: not delivered",
    "Approval requested for github_issue",
    "Approval approved",
    "Tool web_search started",
    "Tool web_search failed (rate_limited)",
    "Tool web_search succeeded",
    "Result text",
    "Artifact report.md published",
    "Artifact report.md is missing",
  ]);
});

test("a replayed event replaces itself, and nothing to add keeps the same map", () => {
  const first = mergeEvents(new Map(), [status(1, "queued", "running")]);
  const again = mergeEvents(first, [
    status(1, "queued", "running"),
    started(2),
  ]);
  assert.deepEqual([...again.keys()], [1, 2]);
  assert.notEqual(again, first);
  assert.equal(first.size, 1);
  assert.equal(mergeEvents(again, []), again);
});

test("the timeline is in sequence order, whatever order events arrived in", () => {
  const events = mergeEvents(new Map(), [
    started(3),
    status(1, "queued", "running"),
  ]);
  const merged = mergeEvents(events, [completed(2, "succeeded")]);
  assert.deepEqual(
    toTimeline(merged.values()).map((item) => item.sequence),
    [1, 2, 3],
  );
});

test("the newest published artifact is the result, and none is null", () => {
  const other = "55555555-5555-4555-8555-555555555555";
  const events = [
    published(4, "draft.md"),
    published(9, "final.md", other),
    status(12, "verifying", "succeeded"),
  ];
  assert.deepEqual(latestPublished(events), { id: other, name: "final.md" });
  assert.deepEqual(latestPublished(events.slice(0, 1)), {
    id: ARTIFACT,
    name: "draft.md",
  });
  assert.equal(latestPublished([status(1, "queued", "running")]), null);
});

test("only tool-use events count toward the tool uses' version", () => {
  assert.equal(
    toolEventCount([
      started(1),
      completed(2, "succeeded"),
      status(3, "running", "verifying"),
      published(4, "r.md"),
    ]),
    2,
  );
  assert.equal(toolEventCount([]), 0);
});

test("a live piece extends the text only where it continues it", () => {
  const first = withDelta(null, { segment: 0, offset: 0, text: "Hello" });
  assert.deepEqual(first, { segment: 0, text: "Hello", joined: false });
  assert.deepEqual(
    withDelta(first, { segment: 0, offset: 5, text: " world" }),
    {
      segment: 0,
      text: "Hello world",
      joined: false,
    },
  );
  // A duplicate, or a piece the text already holds, changes nothing.
  assert.equal(withDelta(first, { segment: 0, offset: 0, text: "Hel" }), first);
  assert.equal(
    withDelta(first, { segment: 0, offset: 0, text: "Hello" }),
    first,
  );
  // A gap after a reconnect: the piece is shown as joined partway.
  assert.deepEqual(withDelta(first, { segment: 0, offset: 9, text: "later" }), {
    segment: 0,
    text: "Hellolater",
    joined: true,
  });
  // WRUN-15: a piece that overlaps the text is appended whole and marked joined. The service's
  // ResultTap (services/agent/src/autobots/adapters/result_stream.py) sends contiguous pieces from
  // `call.sent` and drops one it already sent, and the stored artifact replaces the live text.
  assert.deepEqual(
    withDelta(first, { segment: 0, offset: 3, text: "lo world" }),
    { segment: 0, text: "Hellolo world", joined: true },
  );
  // A new segment starts over, joined when it doesn't start at its beginning.
  assert.deepEqual(
    withDelta(first, { segment: 1, offset: 4, text: "joined" }),
    {
      segment: 1,
      text: "joined",
      joined: true,
    },
  );
  assert.deepEqual(withDelta(first, { segment: 1, offset: 0, text: "next" }), {
    segment: 1,
    text: "next",
    joined: false,
  });
});
