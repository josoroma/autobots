/**
 * Money, wall times, relative times and instants for display, with one rule each for every screen
 * (R-37, XDUP-17, XWEB-09). Pure and JSX-free, so `node --test` covers it.
 *
 * Amounts stay integer micro-USD until shown (PRD-Development-Harness DH-06), and a shown amount is
 * never rounded, so a spend or a limit never reads smaller than it is. Wall times and relative times
 * round half away from zero to the smallest unit they show, except time left before a deadline,
 * which rounds down. Whether a figure is an estimate stays the caller's to say (PRD-Design-System
 * DS-04).
 */

/** Micro-USD in one US dollar. */
export const MICRO_USD = 1_000_000;

const MICRO_DIGITS = 6;
const CENT_DIGITS = 2;

function roundHalfAway(value: number): number {
  return Math.sign(value) * Math.round(Math.abs(value));
}

function twoDigits(value: number): string {
  return String(value).padStart(2, "0");
}

/**
 * US$ with two decimals, and more only when the exact amount has them, up to micro-USD's six:
 * 250_000 is US$0.25 and 1_234 is US$0.001234. A fractional micro-USD, which the contract's integers
 * rule out, rounds away from zero.
 */
export function formatUsd(micro: number): string {
  const sign = micro < 0 ? "-" : "";
  const whole = Math.ceil(Math.abs(micro));
  const dollars = Math.floor(whole / MICRO_USD);
  const fraction = String(whole % MICRO_USD)
    .padStart(MICRO_DIGITS, "0")
    .replace(/0+$/, "")
    .padEnd(CENT_DIGITS, "0");
  return `${sign}US$${dollars}.${fraction}`;
}

/** A wall time: "7s" under a minute, "1m 05s" under an hour, then "2h 00m". Never negative. */
export function formatDuration(seconds: number): string {
  const total = roundHalfAway(Math.max(seconds, 0));
  if (total < 3_600) {
    const minutes = Math.floor(total / 60);
    const rest = total % 60;
    return minutes === 0 ? `${rest}s` : `${minutes}m ${twoDigits(rest)}s`;
  }
  const minutes = roundHalfAway(Math.max(seconds, 0) / 60);
  return `${Math.floor(minutes / 60)}h ${twoDigits(minutes % 60)}m`;
}

const RELATIVE = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const UNITS: readonly (readonly [Intl.RelativeTimeFormatUnit, number])[] = [
  ["day", 86_400_000],
  ["hour", 3_600_000],
  ["minute", 60_000],
];

/**
 * How long before or after `now` an instant is, in whole words of the largest unit reached, such as
 * "5 minutes ago", "in 3 hours" or "yesterday"; under a minute either way is "just now". `now` is
 * epoch milliseconds, taken when the screen read its data rather than during render.
 */
export function formatRelative(iso: string, now: number): string {
  const elapsed = Date.parse(iso) - now;
  for (const [unit, size] of UNITS) {
    if (Math.abs(elapsed) >= size) {
      return RELATIVE.format(roundHalfAway(elapsed / size), unit);
    }
  }
  return "just now";
}

const COUNTDOWN = new Intl.RelativeTimeFormat("en", { numeric: "always" });

/**
 * Time left before a deadline, such as an approval's expiry, rounded down so a person never believes
 * they have longer than they do: 4m40s left is "in 4 minutes", and under a minute is "in less than a
 * minute". Days stay counted, "in 1 day", since "tomorrow" could read as all of tomorrow. A deadline
 * reached or past reads as formatRelative says other past times.
 */
export function untilDeadline(iso: string, now: number): string {
  const left = Date.parse(iso) - now;
  if (!(left > 0)) return formatRelative(iso, now);
  for (const [unit, size] of UNITS) {
    if (left >= size) return COUNTDOWN.format(Math.floor(left / size), unit);
  }
  return "in less than a minute";
}

/** An instant as its UTC ISO string, the same on every screen. One that can't be read stays as sent. */
export function formatInstant(iso: string): string {
  const when = new Date(iso);
  return Number.isNaN(when.getTime()) ? iso : when.toISOString();
}
