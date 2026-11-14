import assert from "node:assert/strict";

import {
  RunConnection,
  type RunView,
  type StreamHandlers,
} from "../../lib/run-connection.ts";

// Fakes for the run page's connection: a server that answers each path from arranged replies, a
// stream and a clock the test drives, and fixtures that the generated parsers accept. Shared by
// run-connection.test.ts and run-connection-stream.test.ts (refactor plan R-28).

let runs = 0;
/** A run id of its own for each test, so no read is shared with another test's. */
export function newRun(): string {
  runs += 1;
  return `11111111-1111-4111-8111-${String(runs).padStart(12, "0")}`;
}

export function snapshot(run: string, cursor: number, status = "queued") {
  return {
    schema_version: 1,
    run: {
      schema_version: 1,
      version: 1,
      id: run,
      workspace_id: "22222222-2222-4222-8222-222222222222",
      parent_run_id: null,
      status,
      created_at: "2026-11-14T00:00:00+00:00",
      updated_at: "2026-11-14T00:00:00+00:00",
      budget: {
        spent_micro_usd: 0,
        reserved_micro_usd: 0,
        limit_micro_usd: 1000,
      },
    },
    objective: "Arranged",
    criteria: [],
    plan: null,
    artifacts: [],
    usage: {
      model_calls: 0,
      tool_dispatches: 0,
      repairs: 0,
      plan_revisions: 0,
      input_tokens: 0,
      output_tokens: 0,
    },
    stop_reason: null,
    verification: null,
    expert: null,
    assignments: [],
    outstanding: {
      uncertain_calls: 0,
      unknown_effects: 0,
      unreported_charges: 0,
    },
    unknown_operations: [],
    cursor,
    role_map: [],
    budgets: { context_tokens: 1000, max_output_tokens_per_call: 100 },
    can_continue: false,
    metered_tool_calls: 0,
    metered_tool_call_limit: 0,
  };
}

export function event(run: string, sequence: number, current = "running") {
  return {
    schema_version: 1,
    run_id: run,
    sequence,
    causal_ids: [],
    occurred_at: "2026-11-14T00:00:00+00:00",
    payload: { type: "run.status_changed", previous: "queued", current },
  };
}

export function eventPage(
  run: string,
  events: unknown[],
  next: number,
  gap = false,
) {
  return { schema_version: 1, run_id: run, events, next_cursor: next, gap };
}

export const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

export type Answer = () => Response | Promise<Response>;

/** Answers each path from its queue of arranged replies, and records every request. */
export class Server {
  readonly calls: { url: string; method: string }[] = [];
  readonly #answers = new Map<string, Answer[]>();

  answer(url: string, ...answers: Answer[]): void {
    this.#answers.set(url, [...(this.#answers.get(url) ?? []), ...answers]);
  }

  asked(url: string): number {
    return this.calls.filter((call) => call.url === url).length;
  }

  readonly fetch: typeof globalThis.fetch = async (input, init) => {
    const url = String(input);
    this.calls.push({ url, method: init?.method ?? "GET" });
    const next = this.#answers.get(url)?.shift();
    if (next === undefined) throw new Error(`nothing arranged for ${url}`);
    return next();
  };
}

/** A reply the test releases when it chooses. */
export function held(): { answer: Answer; release: (reply: Response) => void } {
  let release: (reply: Response) => void = () => undefined;
  const reply = new Promise<Response>((done) => {
    release = done;
  });
  return { answer: () => reply, release };
}

export interface FakeStream {
  url: string;
  on: StreamHandlers;
  closed: boolean;
}

export interface Timer {
  ms: number;
  run: () => void;
  cancelled: boolean;
  fired: boolean;
}

export interface Arranged {
  run: string;
  base: string;
  server: Server;
  streams: FakeStream[];
  timers: Timer[];
  changes: RunView[];
  reports: { event: string; name: string }[];
  connection: RunConnection;
  /** Timers neither cancelled nor fired. */
  waiting(): Timer[];
  /** Fires the only waiting timer. */
  fire(): void;
}

export function arrange(
  options: {
    wanted?: boolean;
    open?: (url: string, on: StreamHandlers) => { close(): void };
  } = {},
): Arranged {
  const run = newRun();
  const server = new Server();
  const streams: FakeStream[] = [];
  const timers: Timer[] = [];
  const changes: RunView[] = [];
  const reports: { event: string; name: string }[] = [];
  const waiting = () =>
    timers.filter((timer) => !timer.cancelled && !timer.fired);
  const connection = new RunConnection({
    runId: run,
    fetch: server.fetch,
    open:
      options.open ??
      ((url, on) => {
        const stream: FakeStream = { url, on, closed: false };
        streams.push(stream);
        return {
          close: () => {
            stream.closed = true;
          },
        };
      }),
    later: (run, ms) => {
      const timer: Timer = { ms, run, cancelled: false, fired: false };
      timers.push(timer);
      return () => {
        timer.cancelled = true;
      };
    },
    onChange: (view) => changes.push(view),
    streamWanted: () => options.wanted ?? true,
    report: (record) => reports.push(record),
  });
  return {
    run,
    base: `/api/v1/runs/${run}`,
    server,
    streams,
    timers,
    changes,
    reports,
    connection,
    waiting,
    fire: () => {
      const due = waiting();
      assert.equal(due.length, 1, "one timer waits");
      const timer = due[0];
      if (timer === undefined) return;
      timer.fired = true;
      timer.run();
    },
  };
}

export const tick = () => new Promise((resolve) => setImmediate(resolve));

export async function until(check: () => boolean, what: string): Promise<void> {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    if (check()) return;
    await tick();
  }
  assert.fail(`never happened: ${what}`);
}

/** Lets every reply that can settle settle. */
export async function settle(): Promise<void> {
  for (let attempt = 0; attempt < 30; attempt += 1) await tick();
}

/** A connection showing a snapshot at `cursor`, with its stream open and live. */
export async function live(cursor: number, options: { wanted?: boolean } = {}) {
  const arranged = arrange(options);
  const { run, base, server, connection, streams } = arranged;
  server.answer(`${base}/workspace`, () => json(200, snapshot(run, cursor)));
  server.answer(`${base}/events?after=0`, () =>
    json(200, eventPage(run, [], cursor)),
  );
  server.answer(`${base}/events?after=${cursor}`, () =>
    json(200, eventPage(run, [], cursor)),
  );
  connection.start();
  await until(() => streams.length === 1, "the stream opened");
  streams[0]?.on.open();
  return { ...arranged, stream: streams[0] };
}
