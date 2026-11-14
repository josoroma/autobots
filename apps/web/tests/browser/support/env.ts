/**
 * The values a spec's runner arranges, read when a test first uses one (TWEB-14). A missing value
 * fails with its name, so an unavailable prerequisite doesn't read as a product failure, the
 * distinction AGENTS.md draws between exit codes 2 and 1. Nothing is read at import, so listing
 * the suites needs no environment.
 */
import { join } from "node:path";

/** A value the runner should have arranged and didn't. */
export class PrerequisiteMissing extends Error {
  constructor(name: string) {
    super(`${name} is not set; run this spec through its runner`);
    this.name = "PrerequisiteMissing";
  }
}

/** A value the runner arranges. An empty value counts as missing. */
export function need(name: string): string {
  const value = process.env[name];
  if (value === undefined || value === "") throw new PrerequisiteMissing(name);
  return value;
}

/** A value with a usable default, such as an output directory. */
export function optional(name: string, fallback: string): string {
  const value = process.env[name];
  return value === undefined || value === "" ? fallback : value;
}

/** A comma-separated list the runner arranges, such as a fixture's run IDs. */
export function needList(name: string): string[] {
  return need(name).split(",");
}

/**
 * A spec's arranged values by its own names, each read with `need` on first use. Read inside a
 * test or hook, never at import.
 */
export function arranged<const Names extends Record<string, string>>(
  names: Names,
): Readonly<Record<keyof Names, string>> {
  const values = {};
  for (const [key, name] of Object.entries(names)) {
    Object.defineProperty(values, key, {
      enumerable: true,
      get: () => need(name),
    });
  }
  return values as Readonly<Record<keyof Names, string>>;
}

/** The web app's address, which the runners pass to the browser suites. */
export function webOrigin(): string {
  return new URL(need("AUTOBOTS_WEB_URL")).origin;
}

/**
 * Where a screenshot goes: the runner's screenshots directory, or Playwright's ignored output
 * directory when a spec runs by hand.
 */
export function screenshotPath(file: string): string {
  return join(
    optional("AUTOBOTS_WEB_SCREENSHOTS", "test-results/screenshots"),
    file,
  );
}
