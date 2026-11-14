import assert from "node:assert/strict";
import { test } from "node:test";

import { withDelta } from "../../lib/run-connection.ts";
import {
  event,
  eventPage,
  held,
  json,
  live,
  settle,
  snapshot,
  until,
} from "./run-connection-fakes.ts";

// The run page's stream: refreshes share one queue and never show an older snapshot over a newer
// one, an error reconnects from the current cursor with a backoff, and the end frame closes it
// (WRUN-02, WRUN-04, refactor plan R-28).

test("refreshes in flight coalesce, and a snapshot older than the one shown is discarded", async () => {
  const { run, base, server, connection, stream, changes } = await live(2);
  const first = held();
  server.answer(`${base}/workspace`, first.answer, () =>
    json(200, snapshot(run, 5, "paused")),
  );
  const before = server.asked(`${base}/workspace`);
  stream?.on.frame("run", JSON.stringify(event(run, 3)));
  stream?.on.frame("run", JSON.stringify(event(run, 4)));
  connection.refresh();
  stream?.on.frame("gap", "{}");
  await settle();
  assert.equal(server.asked(`${base}/workspace`), before + 1);
  // The held reply is older than the shown snapshot (cursor 2), as a reply that lost a race is.
  first.release(json(200, snapshot(run, 1, "succeeded")));
  await until(
    () => server.asked(`${base}/workspace`) === before + 2,
    "the queued refresh",
  );
  await until(
    () =>
      connection.view.load.kind === "ready" &&
      connection.view.load.snapshot.cursor === 5,
    "the newer snapshot",
  );
  const shown = changes.flatMap((view) =>
    view.load.kind === "ready" ? [view.load.snapshot.run.status] : [],
  );
  assert.ok(!shown.includes("succeeded"), "the older snapshot was shown");
  await settle();
  assert.equal(server.asked(`${base}/workspace`), before + 2);
  assert.deepEqual([...connection.view.events.keys()], [3, 4]);
  assert.equal(connection.view.gap, true);
});

test("a stream error reconnects from the current cursor after a backoff, and opening resets it", async () => {
  const { run, base, server, connection, streams, waiting, fire } =
    await live(2);
  streams[0]?.on.frame("cursor", JSON.stringify({ cursor: 5 }));
  streams[0]?.on.frame("cursor", JSON.stringify({ cursor: "NaN" }));
  streams[0]?.on.error();
  assert.equal(streams[0]?.closed, true);
  const load = connection.view.load;
  assert.equal(load.kind === "ready" && load.connection, "reconnecting");
  assert.deepEqual(
    waiting().map((timer) => timer.ms),
    [1000],
  );
  server.answer(`${base}/workspace`, () => json(200, snapshot(run, 5)));
  server.answer(`${base}/events?after=5`, () =>
    json(200, eventPage(run, [], 5)),
  );
  fire();
  await until(() => streams.length === 2, "the stream reopened");
  assert.equal(streams[1]?.url, `${base}/events/stream?after=5`);
  streams[1]?.on.open();
  streams[1]?.on.error();
  assert.deepEqual(
    waiting().map((timer) => timer.ms),
    [1000],
  );
});

test("frames from a stream that was replaced are ignored", async () => {
  const { run, base, server, connection, streams, fire } = await live(2);
  streams[0]?.on.error();
  server.answer(`${base}/workspace`, () => json(200, snapshot(run, 2)));
  server.answer(`${base}/events?after=2`, () =>
    json(200, eventPage(run, [], 2)),
  );
  fire();
  await until(() => streams.length === 2, "the stream reopened");
  const asked = server.calls.length;
  streams[0]?.on.frame("run", JSON.stringify(event(run, 7)));
  streams[0]?.on.error();
  await settle();
  assert.equal(server.calls.length, asked);
  assert.equal(connection.view.events.has(7), false);
});

test("a refusal while a snapshot is shown replaces it and closes the stream", async () => {
  const { run, base, server, connection, stream, waiting } = await live(2);
  server.answer(`${base}/workspace`, () =>
    json(401, { code: "not_signed_in", message: "Sign in." }),
  );
  stream?.on.frame("run", JSON.stringify(event(run, 3)));
  await until(() => connection.view.load.kind === "signed_out", "signed out");
  assert.equal(stream?.closed, true);
  assert.equal(waiting().length, 0);
});

test("the end frame closes the stream and says nothing more is expected", async () => {
  const { connection, stream, waiting } = await live(2);
  stream?.on.frame("end", "{}");
  assert.equal(stream?.closed, true);
  const load = connection.view.load;
  assert.equal(load.kind === "ready" && load.connection, "ended");
  assert.equal(waiting().length, 0);
});

test("live text shows only when streaming is wanted", async () => {
  const delta = (run: string) => ({
    ...event(run, 9),
    payload: { type: "result.text.delta", segment: 1, offset: 0, text: "Hi" },
  });
  const shown = await live(2);
  shown.stream?.on.frame("live", JSON.stringify(delta(shown.run)));
  assert.deepEqual(shown.connection.view.live, {
    segment: 1,
    text: "Hi",
    joined: false,
  });
  assert.equal(shown.connection.view.events.has(9), false);
  const hidden = await live(2, { wanted: false });
  hidden.stream?.on.frame("live", JSON.stringify(delta(hidden.run)));
  assert.equal(hidden.connection.view.live, null);
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
  assert.equal(withDelta(first, { segment: 0, offset: 0, text: "Hel" }), first);
  assert.deepEqual(withDelta(first, { segment: 0, offset: 9, text: "later" }), {
    segment: 0,
    text: "Hellolater",
    joined: true,
  });
  assert.deepEqual(
    withDelta(first, { segment: 1, offset: 4, text: "joined" }),
    {
      segment: 1,
      text: "joined",
      joined: true,
    },
  );
});
