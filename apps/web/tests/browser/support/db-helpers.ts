/**
 * The tests/db helpers some browser tests run to arrange the disposable stack while a page watches
 * (TWEB-11). Each call has a timeout and runs off the event loop, so Playwright's own timeout can
 * still fire, and a failure names the helper with its exit and the end of its stderr. The helpers
 * act only on the disposable target the runner provides (AGENTS.md).
 */
import { execFile, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { createInterface } from "node:readline";

import { need, optional } from "./env.ts";

type Parse<T> = (value: unknown) => T;

const REPOSITORY = join(__dirname, "../../../../..");
const DEFAULT_TIMEOUT_MS = 60_000;

/** A tests/db helper's path, resolved from the repository as appearance.spec.ts resolves luma.css. */
export function helperPath(name: string): string {
  const path = join(REPOSITORY, "tests/db", name);
  if (!existsSync(path)) throw new Error(`tests/db/${name} doesn't exist`);
  return path;
}

function helperEnv(extra: Record<string, string>): NodeJS.ProcessEnv {
  return {
    ...process.env,
    AUTOBOTS_DATABASE_URL: need("AUTOBOTS_TEST_RUNTIME_URL"),
    PYTHONPATH: optional("AUTOBOTS_TEST_PYTHONPATH", ""),
    ...extra,
  };
}

function tail(text: string): string {
  return text.trim().split("\n").slice(-12).join("\n");
}

function parseLine<T>(name: string, line: string, parse: Parse<T>): T {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    throw new Error(
      `tests/db/${name} printed a line that isn't JSON: ${line.slice(0, 300)}`,
    );
  }
  return parse(value);
}

/** Runs a helper to completion and parses the last line it prints as JSON. */
export function runDbHelper<T>(
  name: string,
  args: readonly string[],
  parse: Parse<T>,
  {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    env = {},
  }: { timeoutMs?: number; env?: Record<string, string> } = {},
): Promise<T> {
  return new Promise((resolve, reject) => {
    execFile(
      need("AUTOBOTS_TEST_PYTHON"),
      [helperPath(name), ...args],
      { env: helperEnv(env), encoding: "utf8", timeout: timeoutMs },
      (error, stdout, stderr) => {
        if (error !== null) {
          const how = error.killed
            ? `didn't finish within ${timeoutMs} ms`
            : `failed (${error.code ?? error.signal ?? "no exit code"})`;
          reject(new Error(`tests/db/${name} ${how}:\n${tail(stderr)}`));
          return;
        }
        const last = stdout.trim().split("\n").at(-1) ?? "";
        try {
          resolve(parseLine(name, last, parse));
        } catch (failure) {
          reject(
            failure instanceof Error ? failure : new Error(String(failure)),
          );
        }
      },
    );
  });
}

/** A helper that keeps running and prints a JSON line per step. */
export interface DbHelperStream {
  /** The next line printed, parsed. Rejects if the helper ends or fails before printing it. */
  next<T>(parse: Parse<T>): Promise<T>;
  /** Stops the helper, if it's still running. */
  stop(): void;
}

/** Starts a helper whose lines a test reads as they come. The `dbStream` fixture stops it. */
export function streamDbHelper(
  name: string,
  args: readonly string[],
  env: Record<string, string> = {},
): DbHelperStream {
  const child = spawn(
    need("AUTOBOTS_TEST_PYTHON"),
    [helperPath(name), ...args],
    {
      env: helperEnv(env),
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  const lines: string[] = [];
  const waiting: {
    take: (line: string) => void;
    fail: (error: Error) => void;
  }[] = [];
  let ended: Error | null = null;
  let stderr = "";
  child.stderr.on("data", (chunk: Buffer) => {
    stderr = tail(stderr + chunk.toString("utf8"));
  });
  createInterface({ input: child.stdout }).on("line", (line) => {
    const waiter = waiting.shift();
    if (waiter) waiter.take(line);
    else lines.push(line);
  });
  const end = (error: Error) => {
    ended ??= error;
    for (const waiter of waiting.splice(0)) waiter.fail(ended);
  };
  child.on("error", (error) =>
    end(new Error(`tests/db/${name} couldn't start: ${error.message}`)),
  );
  child.on("close", (code, signal) =>
    end(
      new Error(
        `tests/db/${name} ended (${code ?? signal}) before printing what was awaited:\n${stderr}`,
      ),
    ),
  );
  return {
    next<T>(parse: Parse<T>): Promise<T> {
      const read = new Promise<T>((resolve, reject) => {
        const take = (line: string) => {
          try {
            resolve(parseLine(name, line, parse));
          } catch (failure) {
            reject(
              failure instanceof Error ? failure : new Error(String(failure)),
            );
          }
        };
        const buffered = lines.shift();
        if (buffered !== undefined) take(buffered);
        else if (ended !== null) reject(ended);
        else waiting.push({ take, fail: reject });
      });
      // Surfaces when the test awaits it, never as an unhandled rejection before that.
      read.catch(() => undefined);
      return read;
    },
    stop(): void {
      if (child.exitCode === null && child.signalCode === null) child.kill();
    },
  };
}

type Field = "string" | "number";
type Shape = Record<string, Field>;
type Shaped<S extends Shape> = {
  [K in keyof S]: S[K] extends "number" ? number : string;
};

/** A parser for a helper's printed object, checking the named fields and ignoring the rest. */
export function objectOf<const S extends Shape>(shape: S): Parse<Shaped<S>> {
  return (value) => {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      throw new Error(`expected an object, got ${JSON.stringify(value)}`);
    }
    const record = value as Record<string, unknown>;
    for (const [key, type] of Object.entries(shape)) {
      if (typeof record[key] !== type) {
        throw new Error(
          `expected ${key} to be a ${type} in ${JSON.stringify(value)}`,
        );
      }
    }
    return record as Shaped<S>;
  };
}

/** A parser for a helper's printed list, each item parsed by `item`. */
export function arrayOf<T>(item: Parse<T>): Parse<T[]> {
  return (value) => {
    if (!Array.isArray(value))
      throw new Error(`expected a list, got ${JSON.stringify(value)}`);
    return value.map(item);
  };
}
