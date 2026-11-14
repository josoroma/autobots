import assert from "node:assert/strict";
import { test } from "node:test";

import {
  arrange,
  event,
  eventPage,
  held,
  json,
  live,
  settle,
  snapshot,
  until,
  type Answer,
} from "./run-connection-fakes.ts";

// The run page's reads, driven through fakes for the server, the stream and the clock: it reads the
// snapshot, replays and then streams; it stops on a refusal or a mismatch, backs off on an outage,
// and only reads (WRUN-02, refactor plan R-28).

test("the snapshot, then the replay, then the stream from where the replay ended", async () => {
  const { run, base, server, connection, streams } = arrange();
  server.answer(`${base}/workspace`, () => json(200, snapshot(run, 2)));
  server.answer(`${base}/events?after=0`, () =>
    json(200, eventPage(run, [event(run, 1), event(run, 2)], 2)),
  );
  server.answer(`${base}/events?after=2`, () =>
    json(200, eventPage(run, [], 2)),
  );
  connection.start();
  await until(() => streams.length === 1, "the stream opened");
  assert.equal(streams[0]?.url, `${base}/events/stream?after=2`);
  assert.deepEqual([...connection.view.events.keys()], [1, 2]);
  assert.equal(connection.view.load.kind, "ready");
  assert.equal(
    connection.view.load.kind === "ready" && connection.view.load.connection,
    "loading",
  );
  streams[0]?.on.open();
  assert.equal(
    connection.view.load.kind === "ready" && connection.view.load.connection,
    "live",
  );
  assert.ok(server.calls.every((call) => call.method === "GET"));
});

test("403 stops with the envelope's message: nothing is read again, replayed or streamed", async () => {
  const { base, server, connection, streams, waiting } = arrange();
  server.answer(`${base}/workspace`, () =>
    json(403, { code: "workspace_required", message: "Choose a workspace." }),
  );
  connection.start();
  await until(() => connection.view.load.kind !== "loading", "a state");
  assert.deepEqual(connection.view.load, {
    kind: "denied",
    message: "Choose a workspace.",
  });
  await settle();
  assert.deepEqual(
    server.calls.map((call) => call.url),
    [`${base}/workspace`],
  );
  assert.equal(waiting().length, 0);
  assert.equal(streams.length, 0);
});

test("401, 404, 422 and a drifted snapshot each stop without trying again", async () => {
  const cases: [Answer, string][] = [
    [
      () => json(401, { code: "not_signed_in", message: "Sign in." }),
      "signed_out",
    ],
    [() => json(404, { code: "run_not_found", message: "No." }), "not_found"],
    [
      () => json(422, { code: "validation_error", message: "No." }),
      "not_found",
    ],
    [() => json(200, { schema_version: 1 }), "invalid"],
    [() => new Response("<html>", { status: 200 }), "invalid"],
  ];
  for (const [answer, kind] of cases) {
    const { base, server, connection, streams, waiting } = arrange();
    server.answer(`${base}/workspace`, answer);
    connection.start();
    await until(() => connection.view.load.kind !== "loading", "a state");
    assert.equal(connection.view.load.kind, kind);
    await settle();
    assert.equal(server.calls.length, 1, kind);
    assert.equal(waiting().length, 0, kind);
    assert.equal(streams.length, 0, kind);
  }
});

test("a drifted snapshot names the contract's path, never a value from the reply", async () => {
  const { run, base, server, connection } = arrange();
  server.answer(`${base}/workspace`, () =>
    json(200, { ...snapshot(run, 1), cursor: "secret-ish" }),
  );
  connection.start();
  await until(() => connection.view.load.kind === "invalid", "invalid");
  const load = connection.view.load;
  assert.ok(load.kind === "invalid" && load.path.includes("cursor"));
  assert.ok(!JSON.stringify(load).includes("secret-ish"));
});

test("an outage waits 1, 2 and 4 seconds between attempts, reading nothing meanwhile, and recovers", async () => {
  const { run, base, server, connection, streams, waiting, fire } = arrange();
  const outage = () =>
    json(503, { code: "service_unavailable", message: "Unavailable." });
  server.answer(`${base}/workspace`, outage, outage, outage, () =>
    json(200, snapshot(run, 0)),
  );
  server.answer(`${base}/events?after=0`, () =>
    json(200, eventPage(run, [], 0)),
  );
  connection.start();
  for (const [attempt, delayMs] of [
    [1, 1000],
    [2, 2000],
    [3, 4000],
  ] as const) {
    await until(
      () =>
        connection.view.load.kind === "retrying" &&
        connection.view.load.attempt === attempt,
      `attempt ${attempt}`,
    );
    assert.deepEqual(connection.view.load, {
      kind: "retrying",
      attempt,
      delayMs,
      status: 503,
    });
    assert.deepEqual(
      waiting().map((timer) => timer.ms),
      [delayMs],
    );
    await settle();
    assert.equal(server.asked(`${base}/workspace`), attempt);
    fire();
  }
  await until(() => streams.length === 1, "the stream opened");
  assert.equal(connection.view.load.kind, "ready");
});

test("Retry reads at once and cancels the wait", async () => {
  const { run, base, server, connection, streams, waiting } = arrange();
  server.answer(
    `${base}/workspace`,
    () => json(503, { code: "service_unavailable", message: "Unavailable." }),
    () => json(200, snapshot(run, 0)),
  );
  server.answer(`${base}/events?after=0`, () =>
    json(200, eventPage(run, [], 0)),
  );
  connection.start();
  await until(() => connection.view.load.kind === "retrying", "retrying");
  connection.retry();
  await until(() => streams.length === 1, "the stream opened");
  assert.equal(waiting().length, 0);
  assert.equal(server.asked(`${base}/workspace`), 2);
});

test("a drifted replay page stops the page with the page's contract path", async () => {
  const { run, base, server, connection, streams } = arrange();
  server.answer(`${base}/workspace`, () => json(200, snapshot(run, 1)));
  server.answer(`${base}/events?after=0`, () =>
    json(200, { schema_version: 1, run_id: run, events: [], gap: false }),
  );
  connection.start();
  await until(() => connection.view.load.kind === "invalid", "invalid");
  const load = connection.view.load;
  assert.ok(load.kind === "invalid" && load.path.includes("next_cursor"));
  assert.equal(streams.length, 0);
});

test("the replay skips unknown events, marks a gap, and stops when the cursor stops advancing", async () => {
  const { run, base, server, connection, streams } = arrange();
  server.answer(`${base}/workspace`, () => json(200, snapshot(run, 4)));
  server.answer(`${base}/events?after=0`, () =>
    json(
      200,
      eventPage(
        run,
        [event(run, 3), { ...event(run, 4), payload: { type: "future.kind" } }],
        4,
        true,
      ),
    ),
  );
  server.answer(`${base}/events?after=4`, () =>
    json(200, eventPage(run, [], 4)),
  );
  connection.start();
  await until(() => streams.length === 1, "the stream opened");
  assert.deepEqual([...connection.view.events.keys()], [3]);
  assert.equal(connection.view.gap, true);
  assert.equal(server.calls.length, 3);
});

test("an unexpected failure is caught, reported by its name only, and tried again", async () => {
  const { run, base, server, connection, reports, waiting } = arrange({
    open: () => {
      throw new TypeError("arranged detail");
    },
  });
  server.answer(`${base}/workspace`, () => json(200, snapshot(run, 0)));
  server.answer(`${base}/events?after=0`, () =>
    json(200, eventPage(run, [], 0)),
  );
  connection.start();
  await until(() => reports.length === 1, "a report");
  assert.deepEqual(reports, [
    { event: "web.run_workspace_error", name: "TypeError" },
  ]);
  const load = connection.view.load;
  assert.equal(load.kind === "ready" && load.connection, "reconnecting");
  assert.deepEqual(
    waiting().map((timer) => timer.ms),
    [1000],
  );
});

test("closing stops reading and listening, and nothing it sent could change the run", async () => {
  const { run, base, server, connection, stream, changes, waiting } =
    await live(2);
  const first = held();
  server.answer(`${base}/workspace`, first.answer);
  stream?.on.frame("run", JSON.stringify(event(run, 3)));
  await settle();
  connection.close();
  const seen = changes.length;
  first.release(json(200, snapshot(run, 3, "paused")));
  stream?.on.frame("run", JSON.stringify(event(run, 4)));
  connection.refresh();
  connection.retry();
  await settle();
  assert.equal(stream?.closed, true);
  assert.equal(changes.length, seen);
  assert.equal(waiting().length, 0);
  assert.ok(server.calls.every((call) => call.method === "GET"));
});
