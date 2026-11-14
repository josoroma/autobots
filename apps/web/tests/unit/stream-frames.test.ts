import assert from "node:assert/strict";
import { test } from "node:test";

import {
  parseCursorFrame,
  parseEventFrame,
  splitEventPage,
} from "../../lib/stream-frames.ts";

const RUN = "11111111-1111-4111-8111-111111111111";
const event = (sequence: number) => ({
  schema_version: 1,
  run_id: RUN,
  sequence,
  causal_ids: [],
  occurred_at: "2026-11-05T00:00:00+00:00",
  payload: {
    type: "run.status_changed",
    previous: "queued",
    current: "running",
  },
});

test("a cursor frame gives a safe, non-negative integer", () => {
  assert.equal(parseCursorFrame(JSON.stringify({ cursor: 7 })), 7);
  assert.equal(parseCursorFrame(JSON.stringify({ cursor: 0 })), 0);
});

test("a cursor frame without a usable number is null, never NaN", () => {
  for (const data of [
    JSON.stringify({}),
    JSON.stringify({ cursor: "7" }),
    JSON.stringify({ cursor: -1 }),
    JSON.stringify({ cursor: 1.5 }),
    JSON.stringify({ cursor: 2 ** 60 }),
    "not json",
    undefined,
  ]) {
    assert.equal(parseCursorFrame(data), null);
  }
});

test("an event frame of a known type is parsed, and anything else is null", () => {
  assert.equal(parseEventFrame(JSON.stringify(event(3)))?.sequence, 3);
  assert.equal(
    parseEventFrame(
      JSON.stringify({ ...event(3), payload: { type: "future.kind" } }),
    ),
    null,
  );
  assert.equal(parseEventFrame("{"), null);
});

test("a replay page keeps its known events and counts the skipped ones", () => {
  const raw = {
    schema_version: 1,
    run_id: RUN,
    next_cursor: 9,
    gap: false,
    events: [
      event(1),
      { ...event(2), payload: { type: "future.kind" } },
      event(3),
    ],
  };
  const split = splitEventPage(raw);
  assert.deepEqual(
    split.events.map((item) => item.sequence),
    [1, 3],
  );
  assert.equal(split.skipped, 1);
  assert.equal(split.page.next_cursor, 9);
});

test("a page whose cursor drifted is a contract error, not a cursor of NaN", () => {
  assert.throws(() =>
    splitEventPage({ schema_version: 1, run_id: RUN, gap: false, events: [] }),
  );
  assert.throws(() => splitEventPage("not a page"));
});
