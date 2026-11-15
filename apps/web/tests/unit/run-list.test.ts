/**
 * The runs list's pure parts (PRD-Studio RN-01 to RN-03, R-49, WRUN-05, WRUN-15): the read's query
 * from its filters, each row's state line and spend bar, and Load more appending only to the first
 * page it was read for.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { listRuns, parseRunList, type RunList } from "@autobots/api-client";

import { load, readOf } from "../../lib/load.ts";
import {
  runListQuery,
  spendShare,
  stateLine,
  withMore,
} from "../../lib/runs/list.ts";

const ALL = { group: "all", query: "", profile: "" } as const;

/** The URL the browser asks for with this query. */
async function urlOf(query: Parameters<typeof listRuns>[1]): Promise<string> {
  const asked: string[] = [];
  await load(readOf(listRuns, query), {
    fetch: async (input) => {
      asked.push(String(input));
      return new Response("{}", { status: 503 });
    },
  });
  return asked[0] ?? "";
}

test("defaults send no query string, and each filter and the cursor add theirs", async () => {
  assert.equal(await urlOf(runListQuery(ALL, null)), "/api/v1/runs");
  assert.equal(
    await urlOf(
      runListQuery(
        {
          group: "needs_you",
          query: "  quarter figures ",
          profile: "openrouter_terra",
        },
        "c1",
      ),
    ),
    "/api/v1/runs?group=needs_you&q=quarter+figures&profile=openrouter_terra&cursor=c1",
  );
  assert.equal(
    await urlOf(runListQuery({ ...ALL, query: "   " }, null)),
    "/api/v1/runs",
  );
});

function row(patch: Record<string, unknown>): RunList["runs"][number] {
  const list = parseRunList({
    schema_version: 1,
    has_more: false,
    next_cursor: null,
    total: 1,
    counts: { all: 1, active: 0, needs_you: 0, finished: 1 },
    runs: [
      {
        id: "11111111-1111-4111-8111-111111111111",
        parent_run_id: null,
        status: "queued",
        goal_summary: "Goal",
        created_at: "2026-11-15T00:00:00+00:00",
        updated_at: "2026-11-15T00:00:00+00:00",
        label_kind: "goal",
        label: null,
        stop_reason: null,
        tasks_complete: 0,
        tasks_total: 0,
        profiles: [],
        charged_micro_usd: 0,
        reserved_micro_usd: 0,
        unreported: false,
        limit_micro_usd: 1_000_000,
        ...patch,
      },
    ],
  });
  const [first] = list.runs;
  if (first === undefined) throw new Error("no row");
  return first;
}

test("a row's state says why a run failed, and how far a working run has got", () => {
  assert.equal(stateLine(row({ status: "queued" })), "Queued");
  assert.equal(
    stateLine(row({ status: "failed", stop_reason: "budget_exhausted" })),
    "Failed · budget exhausted",
  );
  assert.equal(stateLine(row({ status: "failed" })), "Failed");
  assert.equal(
    stateLine(row({ status: "running", tasks_complete: 1, tasks_total: 3 })),
    "Running · 1 of 3",
  );
  assert.equal(
    stateLine(row({ status: "verifying", tasks_complete: 3, tasks_total: 3 })),
    "Verifying · 3 of 3",
  );
  assert.equal(stateLine(row({ status: "running" })), "Running");
  assert.equal(
    stateLine(row({ status: "paused", tasks_complete: 1, tasks_total: 3 })),
    "Paused",
  );
});

test("the spend bar is the share of the limit, whole and at most full", () => {
  assert.equal(spendShare(250_000, 1_000_000), 25);
  assert.equal(spendShare(3_000_000, 1_000_000), 100);
  assert.equal(spendShare(1, 3), 33);
  assert.equal(spendShare(5, 0), 0);
});

test("Load more appends to the first page it was read for, and keeps the newest page's facts", () => {
  const base = parseRunList({
    schema_version: 1,
    has_more: true,
    next_cursor: "c1",
    total: 3,
    counts: { all: 3, active: 0, needs_you: 0, finished: 3 },
    runs: [],
  });
  assert.equal(withMore(base, null), base);
  const next = { ...base, has_more: false, next_cursor: null };
  const more = {
    base,
    runs: [row({})],
    next,
    failure: null,
    loading: false,
  };
  const shown = withMore(base, more);
  assert.equal(shown.has_more, false);
  assert.equal(shown.runs.length, 1);
  assert.equal(withMore(base, { ...more, next: null, loading: true }), base);
});
