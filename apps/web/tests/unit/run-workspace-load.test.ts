import assert from "node:assert/strict";
import { test } from "node:test";

import type { LoadFailure } from "../../lib/load.ts";
import {
  retryDelay,
  retryWords,
  shownState,
  stops,
  withConnection,
  withFailure,
  withSnapshot,
  type WorkspaceLoad,
} from "../../lib/run-workspace-load.ts";

// The run page's load states: which failures stop it, how long it waits between attempts, and when a
// snapshot may replace the one shown (WRUN-02, WRUN-04, refactor plan R-28).

interface Snap {
  cursor: number;
  status: string;
}

const snap = (cursor: number, status = "running"): Snap => ({
  cursor,
  status,
});
const LOADING: WorkspaceLoad<Snap> = { kind: "loading" };
const ready = (
  cursor: number,
  connection: "loading" | "live" | "reconnecting" | "ended" = "live",
): WorkspaceLoad<Snap> => ({
  kind: "ready",
  snapshot: snap(cursor),
  connection,
});
const FIRST = { attempt: 1, delayMs: 1000 };

const STOPPED: WorkspaceLoad<Snap>[] = [
  { kind: "signed_out" },
  { kind: "denied", message: "Choose a workspace." },
  { kind: "not_found" },
  { kind: "invalid", schema: "RunWorkspace", path: "RunWorkspace.cursor" },
];

test("attempts wait 1, 2 and 4 seconds, doubling up to 30 seconds", () => {
  assert.deepEqual(
    [1, 2, 3, 4, 5, 6, 7, 40].map(retryDelay),
    [1000, 2000, 4000, 8000, 16000, 30000, 30000, 30000],
  );
});

test("signed out, denied, not found and a mismatch stop the page; only an outage is tried again", () => {
  const failures: [LoadFailure, boolean][] = [
    [{ kind: "signed_out" }, true],
    [{ kind: "denied", message: null }, true],
    [{ kind: "not_found" }, true],
    [{ kind: "out_of_date", schema: null, path: "/api/v1/runs/x" }, true],
    [{ kind: "unavailable", status: 503 }, false],
    [{ kind: "unavailable", status: null }, false],
  ];
  for (const [failure, stopped] of failures) {
    assert.equal(stops(failure), stopped, failure.kind);
  }
});

test("the first snapshot makes the page ready while the stream connects", () => {
  const loads: WorkspaceLoad<Snap>[] = [
    LOADING,
    withFailure(LOADING, { kind: "unavailable", status: 503 }, FIRST),
  ];
  for (const load of loads) {
    assert.deepEqual(withSnapshot(load, snap(3)), {
      kind: "ready",
      snapshot: snap(3),
      connection: "loading",
    });
  }
});

test("a snapshot older than the one shown is discarded, and an equal or newer one replaces it", () => {
  const shown = ready(5);
  assert.equal(withSnapshot(shown, snap(4, "succeeded")), shown);
  assert.deepEqual(withSnapshot(shown, snap(5, "paused")), {
    kind: "ready",
    snapshot: snap(5, "paused"),
    connection: "live",
  });
  assert.deepEqual(withSnapshot(ready(5, "reconnecting"), snap(9)), {
    kind: "ready",
    snapshot: snap(9),
    connection: "reconnecting",
  });
});

test("each refusal and a mismatch become their own state, replacing whatever was shown", () => {
  for (const load of [LOADING, ready(3)]) {
    assert.deepEqual(withFailure(load, { kind: "signed_out" }, FIRST), {
      kind: "signed_out",
    });
    assert.deepEqual(
      withFailure(
        load,
        { kind: "denied", message: "Choose a workspace." },
        FIRST,
      ),
      { kind: "denied", message: "Choose a workspace." },
    );
    assert.deepEqual(withFailure(load, { kind: "not_found" }, FIRST), {
      kind: "not_found",
    });
    assert.deepEqual(
      withFailure(
        load,
        {
          kind: "out_of_date",
          schema: "RunWorkspace",
          path: "RunWorkspace.cursor",
        },
        FIRST,
      ),
      { kind: "invalid", schema: "RunWorkspace", path: "RunWorkspace.cursor" },
    );
  }
});

test("an outage before any snapshot is retrying with its attempt; with one shown it is reconnecting", () => {
  assert.deepEqual(
    withFailure(
      LOADING,
      { kind: "unavailable", status: 503 },
      { attempt: 2, delayMs: 2000 },
    ),
    { kind: "retrying", attempt: 2, delayMs: 2000, status: 503 },
  );
  assert.deepEqual(
    withFailure(ready(3), { kind: "unavailable", status: null }, FIRST),
    { kind: "ready", snapshot: snap(3), connection: "reconnecting" },
  );
});

test("once stopped, a late reply, failure or connection change shows nothing new", () => {
  for (const load of STOPPED) {
    assert.equal(withSnapshot(load, snap(9)), load);
    assert.equal(
      withFailure(load, { kind: "unavailable", status: 503 }, FIRST),
      load,
    );
    assert.equal(withFailure(load, { kind: "signed_out" }, FIRST), load);
    assert.equal(withConnection(load, "live"), load);
  }
});

test("the connection changes only while a snapshot is shown", () => {
  assert.deepEqual(withConnection(ready(2, "loading"), "live"), ready(2));
  assert.deepEqual(withConnection(ready(2), "ended"), ready(2, "ended"));
  assert.equal(withConnection(LOADING, "live"), LOADING);
});

test("what the screen shows instead of the run: loading, the refusal, or an outage that offers Retry", () => {
  assert.deepEqual(shownState(LOADING), { kind: "loading" });
  assert.deepEqual(
    shownState({ kind: "retrying", attempt: 3, delayMs: 4000, status: 503 }),
    { kind: "unavailable", status: 503 },
  );
  assert.deepEqual(
    shownState({
      kind: "invalid",
      schema: "EventPage",
      path: "EventPage.next_cursor",
    }),
    { kind: "out_of_date", schema: "EventPage", path: "EventPage.next_cursor" },
  );
  assert.deepEqual(shownState({ kind: "denied", message: "No." }), {
    kind: "denied",
    message: "No.",
  });
  assert.deepEqual(shownState({ kind: "signed_out" }), { kind: "signed_out" });
  assert.deepEqual(shownState({ kind: "not_found" }), { kind: "not_found" });
  assert.equal(shownState(ready(1)), null);
});

test("the retry note says when the next attempt is", () => {
  assert.equal(retryWords(1000), "Trying again in 1 second.");
  assert.equal(retryWords(2000), "Trying again in 2 seconds.");
  assert.equal(retryWords(30_000), "Trying again in 30 seconds.");
});
