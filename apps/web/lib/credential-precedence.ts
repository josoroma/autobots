// MP-03's source order. No application code calls this: it's the TypeScript half of the US-3.1 parity
// fixture, which contracts/fixtures/ shares with the Python implementation.
import { readFileSync } from "node:fs";
import { isAbsolute, join } from "node:path";

const VARIABLE = "OPENROUTER_API_KEY";

export interface EnvironmentCandidate {
  source: string;
  value: string;
}

export function parseDotenv(text: string): Record<string, string> {
  const values: Record<string, string> = {};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (line === "" || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const index = line.indexOf("=");
    const name = line
      .slice(0, index)
      .trim()
      .replace(/^export /, "")
      .trim();
    let value = line.slice(index + 1).trim();
    const first = value[0];
    if (
      value.length >= 2 &&
      (first === '"' || first === "'") &&
      value.at(-1) === first
    ) {
      value = value.slice(1, -1);
    } else if (value.includes(" #")) {
      value = value.slice(0, value.indexOf(" #")).trimEnd();
    }
    values[name] = value;
  }
  return values;
}

export function dotenvOrder(mode: string): string[] {
  const files = [`.env.${mode}.local`, ".env.local", `.env.${mode}`, ".env"];
  return files.filter((name) => !(name === ".env.local" && mode === "test"));
}

/** The first non-whitespace value wins, and resolution stops there, even if that value is bad. */
export function resolveEnvironmentKey(
  processEnvironment: Record<string, string | undefined>,
  configRoot: string,
  mode: string,
): EnvironmentCandidate | null {
  if (!isAbsolute(configRoot)) {
    throw new Error("the configuration root must be absolute");
  }
  const fromProcess = (processEnvironment[VARIABLE] ?? "").trim();
  if (fromProcess !== "") {
    return { source: "process_environment", value: fromProcess };
  }
  for (const name of dotenvOrder(mode)) {
    let text: string;
    try {
      text = readFileSync(join(configRoot, name), "utf8");
    } catch {
      continue;
    }
    const value = (parseDotenv(text)[VARIABLE] ?? "").trim();
    if (value !== "") {
      return { source: name, value };
    }
  }
  return null;
}
