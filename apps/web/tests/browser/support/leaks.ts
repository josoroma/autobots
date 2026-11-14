/**
 * What must never reach a screen, a reply or the browser, and how a suite proves it (TWEB-08,
 * TWEB-10). nextjs.md and AGENTS.md keep secrets, addresses, local paths and private reasoning out
 * of what the browser receives.
 */
import { expect, type Page, type Response } from "@playwright/test";

/**
 * The canonical deny-list, by kind. Each check applies all of it; a test adds its own values with
 * `extra`, and `allow` names a marker a screen shows on purpose.
 */
export const PRIVATE_MARKERS = {
  providerKeys: ["sk-or-"],
  // A JWT's header always begins so, in exactly this case.
  jwts: ["eyJ"],
  addresses: ["127.0.0.1", "localhost", "postgres://", "postgresql://"],
  localPaths: ["/Users/", "/private/"],
  // The scripted model's private reasoning, and the field OpenRouter returns it in.
  privateReasoning: ["PROTECTED-REASONING", "reasoning_details"],
  // LangGraph checkpoint state. Screens may name checkpoints, never show their contents.
  checkpointState: ["channel_values", "accumulated_output"],
} as const;

export interface PrivateValueOptions {
  /** Names the text in a failure. */
  label?: string;
  /** This test's own values, such as a fixture secret or an ID pattern. */
  extra?: readonly (string | RegExp)[];
  /** Markers this text may hold on purpose. */
  allow?: readonly string[];
  /** Compares lowercased, for a check over text a screen may capitalize. */
  ignoreCase?: boolean;
}

/** Asserts `text` holds no private marker and none of the test's extra values. */
export function expectNoPrivateValues(
  text: string,
  {
    label = "the text",
    extra = [],
    allow = [],
    ignoreCase = false,
  }: PrivateValueOptions = {},
): void {
  const fold = (value: string) => (ignoreCase ? value.toLowerCase() : value);
  const subject = fold(text);
  const markers: (string | RegExp)[] = [
    ...Object.values(PRIVATE_MARKERS)
      .flat()
      .filter((marker) => !allow.includes(marker)),
    ...extra,
  ];
  const found = markers.filter((marker) =>
    typeof marker === "string"
      ? subject.includes(fold(marker))
      : marker.test(subject),
  );
  expect(found.map(String), `${label} holds a private value`).toEqual([]);
}

export interface CapturedBody {
  method: string;
  url: string;
  status: number;
  body: string;
}

function hasNoBody(response: Response): boolean {
  const status = response.status();
  const type = response.headers()["content-type"] ?? "";
  // A redirect carries no body, and an event stream's never ends.
  return (status >= 300 && status <= 399) || type.includes("text/event-stream");
}

/**
 * Starts reading each body `keep` accepts as its response arrives. The returned function awaits
 * every read started so far, so a body still arriving is never skipped, and rejects naming any
 * response whose body couldn't be read.
 */
export function captureBodies(
  page: Page,
  keep: (response: Response) => boolean = () => true,
): () => Promise<CapturedBody[]> {
  const reads: Promise<CapturedBody>[] = [];
  page.on("response", (response) => {
    if (!keep(response) || hasNoBody(response)) return;
    const method = response.request().method();
    const read = response.text().then(
      (body) => ({
        method,
        url: response.url(),
        status: response.status(),
        body,
      }),
      (error: unknown) => {
        throw new Error(
          `${method} ${response.url()}: its body couldn't be read, so it can't be checked: ${String(error)}`,
        );
      },
    );
    // Rejections surface when the reads are awaited, never as unhandled ones before that.
    read.catch(() => undefined);
    reads.push(read);
  });
  return () => Promise.all(reads);
}
