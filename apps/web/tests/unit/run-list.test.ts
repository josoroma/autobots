/**
 * The runs list's pure parts (PRD-Studio RN-01 to RN-03, R-49, WRUN-05, WRUN-15): the read's query
 * from its filters, each row's state line and spend bar, and Load more appending only to the first
 * page it was read for.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { listRuns, parseRunList, type RunList } from "@autobots/api-client";

import { load, readOf } from "../../lib/load.ts";
import { pendingWrite, startDraft } from "../../lib/url-draft.ts";
import {
  mergeRuns,
  runFilterQuery,
  runFilterQueryForUrl,
  runFiltersFrom,
  runFiltersFromQuery,
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

test("the filters come from the page's URL, and a value the list doesn't offer reads as none", () => {
  assert.deepEqual(runFiltersFrom({}), ALL);
  assert.deepEqual(
    runFiltersFrom({
      group: "needs_you",
      q: "fully reported",
      profile: "openrouter_sol",
      run: "11111111-1111-4111-8111-111111111111",
    }),
    { group: "needs_you", query: "fully reported", profile: "openrouter_sol" },
  );
  assert.deepEqual(
    runFiltersFrom({ group: "everything", profile: "openai/gpt-unknown" }),
    ALL,
  );
  // A repeated parameter reads as its first value.
  assert.deepEqual(runFiltersFrom({ group: ["finished", "active"] }), {
    ...ALL,
    group: "finished",
  });
});

test("a filter at its default leaves the URL, so the plain list is plain /runs", () => {
  assert.equal(runFilterQuery(ALL), "");
  assert.equal(
    runFilterQuery({
      group: "active",
      query: " fully reported ",
      profile: "openrouter_terra",
    }),
    "group=active&q=fully+reported&profile=openrouter_terra",
  );
  assert.equal(runFilterQuery({ ...ALL, query: "   " }), "");
  // What the search box shows keeps its spaces until it's written to the URL.
  const typed = runFilterQuery({ ...ALL, query: "fully " }, true);
  assert.equal(typed, "q=fully+");
  assert.deepEqual(runFiltersFromQuery(typed), { ...ALL, query: "fully " });
  assert.equal(runFilterQuery(runFiltersFromQuery(typed)), "q=fully");
});

test("a first page and the pages Load more added show each run once, as the first page has it", () => {
  const first = row({ id: "11111111-1111-4111-8111-111111111111" });
  const newer = { ...first, status: "running" as const };
  const second = row({ id: "22222222-2222-4222-8222-222222222222" });
  const merged = mergeRuns([newer, second], [first, second]);
  assert.deepEqual(
    merged.map((run) => run.id),
    [first.id, second.id],
  );
  assert.equal(merged[0]?.status, "running");
  const base = parseRunList({
    schema_version: 1,
    has_more: false,
    next_cursor: null,
    total: 2,
    counts: { all: 2, active: 1, needs_you: 0, finished: 1 },
    runs: [newer, newer, second],
  });
  assert.deepEqual(
    withMore(base, null).runs.map((run) => run.id),
    [first.id, second.id],
  );
  const shown = withMore(base, {
    base,
    runs: [first],
    next: { ...base, runs: [first] },
    failure: null,
    loading: false,
  });
  assert.deepEqual(
    shown.runs.map((run) => run.id),
    [first.id, second.id],
  );
});

test("opening the list writes no URL: a page's own filters are already in the form the URL keeps", () => {
  for (const params of [
    {},
    { group: "needs_you" },
    { q: "fully reported", profile: "openrouter_sol" },
    { q: "  spaced  ", group: "everything" },
  ]) {
    const opened = runFilterQuery(runFiltersFrom(params));
    assert.equal(pendingWrite(startDraft(opened), runFilterQueryForUrl), null);
  }
  // Typing writes, trimmed, and only what differs from the URL.
  assert.equal(
    runFilterQueryForUrl(runFilterQuery({ ...ALL, query: " fully " }, true)),
    "q=fully",
  );
});
