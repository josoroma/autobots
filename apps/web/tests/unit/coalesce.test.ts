import assert from "node:assert/strict";
import { test } from "node:test";

import { coalesce } from "../../lib/coalesce.ts";

// One read at a time, with one more queued behind it, so the run page's refreshes can't overtake
// each other (WRUN-04, refactor plan R-28).

interface Deferred<T> {
  readonly promise: Promise<T>;
  resolve(value: T): void;
  reject(error: unknown): void;
}

function deferred<T>(): Deferred<T> {
  let resolve: (value: T) => void = () => undefined;
  let reject: (error: unknown) => void = () => undefined;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

/** A read that records each call and settles only when the test says so. */
function arranged(): {
  reads: Deferred<number>[];
  read: () => Promise<number>;
} {
  const reads: Deferred<number>[] = [];
  return {
    reads,
    read: () => {
      const next = deferred<number>();
      reads.push(next);
      return next.promise;
    },
  };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test("one call starts one read and gets its reply", async () => {
  const { reads, read } = arranged();
  const request = coalesce(read);
  const reply = request();
  assert.equal(reads.length, 1);
  reads[0]?.resolve(1);
  assert.equal(await reply, 1);
});

test("calls made while a read is in flight share one more read, which starts after it settles", async () => {
  const { reads, read } = arranged();
  const request = coalesce(read);
  const first = request();
  const second = request();
  const third = request();
  assert.equal(reads.length, 1);
  reads[0]?.resolve(1);
  await tick();
  assert.equal(reads.length, 2);
  reads[1]?.resolve(2);
  assert.deepEqual(await Promise.all([first, second, third]), [1, 2, 2]);
  await tick();
  assert.equal(reads.length, 2);
});

test("a call made after everything settled starts a new read", async () => {
  const { reads, read } = arranged();
  const request = coalesce(read);
  const first = request();
  reads[0]?.resolve(1);
  assert.equal(await first, 1);
  const again = request();
  assert.equal(reads.length, 2);
  reads[1]?.resolve(2);
  assert.equal(await again, 2);
});

test("a failed read still lets the queued one run, and only its own callers see the failure", async () => {
  const { reads, read } = arranged();
  const request = coalesce(read);
  const first = request();
  const second = request();
  reads[0]?.reject(new Error("arranged"));
  await assert.rejects(first, /arranged/);
  await tick();
  assert.equal(reads.length, 2);
  reads[1]?.resolve(2);
  assert.equal(await second, 2);
});

test("never more than one read is in flight, and each reply was read after its call was made", async () => {
  let inFlight = 0;
  let most = 0;
  let started = 0;
  const request = coalesce(async () => {
    inFlight += 1;
    most = Math.max(most, inFlight);
    started += 1;
    const mine = started;
    await tick();
    inFlight -= 1;
    return mine;
  });
  const replies: Promise<number>[] = [];
  const startedWhenAsked: number[] = [];
  for (let index = 0; index < 24; index += 1) {
    startedWhenAsked.push(started);
    replies.push(request());
    if (index % 3 === 0) await Promise.resolve();
    if (index % 5 === 0) await tick();
  }
  const values = await Promise.all(replies);
  assert.equal(most, 1);
  values.forEach((value, index) =>
    assert.ok(
      value > (startedWhenAsked[index] ?? 0),
      `call ${index} was answered by read ${value}, which started before it`,
    ),
  );
  assert.ok(started < replies.length, "calls in flight were not shared");
});
