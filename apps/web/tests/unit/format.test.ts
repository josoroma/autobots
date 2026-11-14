/**
 * Pins the one money, duration, relative-time, deadline and instant format every screen shares.
 * Where screens differed, the result pinned is R-37's choice.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  formatDuration,
  formatInstant,
  formatRelative,
  formatUsd,
  MICRO_USD,
  untilDeadline,
} from "../../lib/format.ts";

test("whole cents read as US$ with two decimals", () => {
  assert.equal(MICRO_USD, 1_000_000);
  assert.equal(formatUsd(0), "US$0.00");
  assert.equal(formatUsd(70_000), "US$0.07");
  assert.equal(formatUsd(180_000), "US$0.18");
  assert.equal(formatUsd(250_000), "US$0.25");
  assert.equal(formatUsd(1_000_000), "US$1.00");
  assert.equal(formatUsd(2_100_000), "US$2.10");
  assert.equal(formatUsd(10_000_000), "US$10.00");
  assert.equal(formatUsd(1_250_000), "US$1.25");
});

test("an amount below a cent is shown exactly, never rounded down to the cent", () => {
  // Two decimals alone would read US$0.00 and US$0.12, less than the amount (R-37).
  assert.equal(formatUsd(1_234), "US$0.001234");
  assert.equal(formatUsd(123_456), "US$0.123456");
  assert.equal(formatUsd(5_000), "US$0.005");
  assert.equal(formatUsd(100), "US$0.0001");
  assert.equal(formatUsd(1), "US$0.000001");
  assert.equal(formatUsd(2_100_500), "US$2.1005");
});

test("an exact amount keeps two decimals, so one run's figures read alike on every screen", () => {
  // The inspector, the run page's Budgets and its Usage share this format (R-37).
  assert.equal(formatUsd(500_000), "US$0.50");
  assert.equal(formatUsd(3_000_000), "US$3.00");
});

test("a negative amount keeps its sign, and a fractional micro-USD rounds up", () => {
  assert.equal(formatUsd(-250_000), "-US$0.25");
  assert.equal(formatUsd(-0), "US$0.00");
  assert.equal(formatUsd(1.2), "US$0.000002");
});

test("a wall time reads in seconds, then minutes and seconds", () => {
  assert.equal(formatDuration(0), "0s");
  assert.equal(formatDuration(7), "7s");
  assert.equal(formatDuration(59), "59s");
  assert.equal(formatDuration(60), "1m 00s");
  assert.equal(formatDuration(65), "1m 05s");
  assert.equal(formatDuration(120), "2m 00s");
  assert.equal(formatDuration(3_599), "59m 59s");
});

test("an hour or more reads in hours and minutes, the minutes rounded half away from zero", () => {
  // The run panel and the workflow list share this, so two hours never reads as 120m 00s (R-37).
  assert.equal(formatDuration(3_600), "1h 00m");
  assert.equal(formatDuration(3_629), "1h 00m");
  assert.equal(formatDuration(3_630), "1h 01m");
  assert.equal(formatDuration(7_200), "2h 00m");
  assert.equal(formatDuration(7_259), "2h 01m");
  assert.equal(formatDuration(7_170), "2h 00m");
  assert.equal(formatDuration(90_000), "25h 00m");
});

test("a fractional or negative wall time rounds to whole seconds, from zero", () => {
  assert.equal(formatDuration(64.5), "1m 05s");
  assert.equal(formatDuration(3_599.6), "1h 00m");
  assert.equal(formatDuration(-5), "0s");
});

const NOW = Date.parse("2026-11-14T12:00:00Z");
const at = (offsetMs: number) => new Date(NOW + offsetMs).toISOString();

test("under a minute either way is just now", () => {
  assert.equal(formatRelative(at(0), NOW), "just now");
  assert.equal(formatRelative(at(-30_000), NOW), "just now");
  assert.equal(formatRelative(at(59_999), NOW), "just now");
  // An expiry 20 s past is just now, never "in 0 min" (WTAP-10).
  assert.equal(formatRelative(at(-20_000), NOW), "just now");
});

test("relative times use whole words, in the largest unit reached", () => {
  assert.equal(formatRelative(at(-60_000), NOW), "1 minute ago");
  assert.equal(formatRelative(at(-5 * 60_000), NOW), "5 minutes ago");
  assert.equal(formatRelative(at(5 * 60_000), NOW), "in 5 minutes");
  assert.equal(formatRelative(at(-3 * 3_600_000), NOW), "3 hours ago");
  assert.equal(formatRelative(at(30 * 3_600_000), NOW), "tomorrow");
  assert.equal(formatRelative(at(-86_400_000), NOW), "yesterday");
  assert.equal(formatRelative(at(-2 * 86_400_000), NOW), "2 days ago");
  assert.equal(formatRelative(at(3 * 86_400_000), NOW), "in 3 days");
});

test("relative times round half away from zero, the same both ways", () => {
  // Math.round alone would make 90 s ago "1 minute ago" but 90 s ahead "in 2 minutes".
  assert.equal(formatRelative(at(-90_000), NOW), "2 minutes ago");
  assert.equal(formatRelative(at(90_000), NOW), "in 2 minutes");
  assert.equal(formatRelative(at(-89_999), NOW), "1 minute ago");
  assert.equal(formatRelative(at(-150 * 60_000), NOW), "3 hours ago");
});

test("time left before a deadline rounds down, so it never reads longer than it is", () => {
  assert.equal(untilDeadline(at(5 * 60_000), NOW), "in 5 minutes");
  assert.equal(untilDeadline(at(5 * 60_000 - 1_000), NOW), "in 4 minutes");
  assert.equal(untilDeadline(at(4 * 60_000 + 40_000), NOW), "in 4 minutes");
  assert.equal(untilDeadline(at(60_000), NOW), "in 1 minute");
  assert.equal(untilDeadline(at(2 * 3_600_000 - 60_000), NOW), "in 1 hour");
  assert.equal(untilDeadline(at(3_600_000), NOW), "in 1 hour");
});

test("under a minute left is less than a minute, never just now", () => {
  assert.equal(untilDeadline(at(59_000), NOW), "in less than a minute");
  assert.equal(untilDeadline(at(1_000), NOW), "in less than a minute");
  assert.equal(untilDeadline(at(1), NOW), "in less than a minute");
});

test("days left are counted, never tomorrow, which could read as all of tomorrow", () => {
  assert.equal(untilDeadline(at(24 * 3_600_000), NOW), "in 1 day");
  assert.equal(untilDeadline(at(30 * 3_600_000), NOW), "in 1 day");
  assert.equal(untilDeadline(at(48 * 3_600_000 - 1_000), NOW), "in 1 day");
  assert.equal(untilDeadline(at(48 * 3_600_000), NOW), "in 2 days");
});

test("a deadline reached or past reads as other past times do", () => {
  assert.equal(untilDeadline(at(0), NOW), "just now");
  assert.equal(untilDeadline(at(-20_000), NOW), "just now");
  assert.equal(untilDeadline(at(-5 * 60_000), NOW), "5 minutes ago");
  assert.equal(untilDeadline(at(-90_000), NOW), "2 minutes ago");
  assert.equal(untilDeadline(at(-86_400_000), NOW), "yesterday");
  assert.equal(untilDeadline("not a time", NOW), "just now");
});

test("an instant reads as its UTC ISO string, and an unreadable one as sent", () => {
  assert.equal(
    formatInstant("2026-11-14T10:00:00.123456+00:00"),
    "2026-11-14T10:00:00.123Z",
  );
  assert.equal(
    formatInstant("2026-11-14T04:00:00-06:00"),
    "2026-11-14T10:00:00.000Z",
  );
  assert.equal(formatInstant("not a time"), "not a time");
});
