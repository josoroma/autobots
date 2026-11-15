/**
 * The run page's reads and event stream, without React (WRUN-02, WRUN-04). It reads the snapshot,
 * replays the events after its cursor, then follows the stream; it stops on a refusal or a contract
 * mismatch, and backs off on an outage. Snapshot reads run one at a time, every refresh shares that
 * queue, and an older snapshot never replaces a newer one. It only reads: closing it, as a browser
 * going away does, never changes the run (PRD-Development-Harness DH-06). The stream, the clock and
 * fetch are passed in, so it also runs under `node --test`. Replay, the stream, backoff,
 * deduplication and live text stay one state machine, since a refusal on any read stops them all.
 */
import {
  getRunWorkspace,
  parseErrorResponse,
  type RunEvent,
  type RunWorkspace,
  type StreamFrame,
} from "@autobots/api-client";
import {
  queryString,
  requestJson,
  type ClientOptions,
} from "@autobots/api-client/runtime";

import { coalesce } from "../coalesce.ts";
import {
  load,
  readOf,
  type Loaded,
  type LoadFailure,
  type Read,
} from "../load.ts";
import { mergeEvents, withDelta, type LiveText } from "./run-events.ts";
import {
  parseCursorFrame,
  parseEventFrame,
  splitEventPage,
  type SplitPage,
  type Stream,
  type StreamHandlers,
} from "./stream.ts";
import {
  retryDelay,
  stops,
  withConnection,
  withFailure,
  withSnapshot,
  type Connection,
  type WorkspaceLoad,
} from "./workspace-load.ts";

export interface RunView {
  load: WorkspaceLoad<RunWorkspace>;
  /** Stored events by sequence, so a replayed one replaces itself rather than repeating. */
  events: ReadonlyMap<number, RunEvent>;
  /** Retained events couldn't fill the range, so the timeline starts later. */
  gap: boolean;
  live: LiveText | null;
}

export const EMPTY_VIEW: RunView = {
  load: { kind: "loading" },
  events: new Map(),
  gap: false,
  live: null,
};

/**
 * listRunEvents's page after `after`, read with `splitEventPage` rather than the generated parser,
 * which would refuse a whole page for one event type this build doesn't know. Such events are
 * skipped and counted instead (Decision 0017 Q13).
 */
async function eventPage(
  client: ClientOptions,
  runId: string,
  after: number,
): Promise<SplitPage> {
  const path = `/v1/runs/${encodeURIComponent(runId)}/events`;
  return splitEventPage(
    await requestJson(
      client,
      "GET",
      `${path}${queryString({ after }, ["after"])}`,
      undefined,
      undefined,
      parseErrorResponse,
    ),
  );
}

export interface RunConnectionOptions {
  runId: string;
  open: (url: string, on: StreamHandlers) => Stream;
  /** Runs `run` after `ms`, and returns what cancels it. */
  later: (run: () => void, ms: number) => () => void;
  onChange: (view: RunView) => void;
  /** Whether live result text is wanted in this browser (PRD-Studio SE-03). Yes by default. */
  streamWanted?: () => boolean;
  /** For tests. The browser's own fetch otherwise. */
  fetch?: typeof globalThis.fetch;
  /** Records an unexpected failure by its name, never its message or a value. */
  report?: (record: { event: string; name: string }) => void;
}

export class RunConnection {
  readonly #options: RunConnectionOptions;
  /** The run's BFF route, under which the event stream is opened; the stream isn't a JSON operation. */
  readonly #base: string;
  readonly #controller = new AbortController();
  readonly #refresh: () => Promise<Loaded<RunWorkspace>>;
  #view: RunView = EMPTY_VIEW;
  /** The newest event sequence the stream and replays have covered. */
  #cursor = 0;
  /** Failed attempts in a row. A frame on the stream resets it, as an open that drops at once proves nothing. */
  #failures = 0;
  #stream: Stream | null = null;
  /** Counts streams opened, so frames from a replaced one are ignored. */
  #generation = 0;
  #cancelWait: (() => void) | null = null;
  #starting = false;
  #closed = false;
  #stopped = false;

  constructor(options: RunConnectionOptions) {
    this.#options = options;
    this.#base = `/api/v1/runs/${encodeURIComponent(options.runId)}`;
    this.#refresh = coalesce(() => this.#readSnapshot());
  }

  get view(): RunView {
    return this.#view;
  }

  /** Reads the snapshot, replays what was missed and follows the stream. */
  start(): void {
    this.#begin();
  }

  /** Reads the snapshot again, in turn with every other refresh, such as after the page's own action. */
  refresh(): void {
    if (this.#halted) return;
    this.#refresh().catch((error: unknown) => this.#lost(error));
  }

  /** The visible Retry: the next attempt now, rather than after its wait. */
  retry(): void {
    if (this.#halted) return;
    this.#clearWait();
    this.#begin();
  }

  /** Stops reading and listening. The run itself is untouched. */
  close(): void {
    this.#closed = true;
    this.#clearWait();
    this.#closeStream();
    this.#controller.abort();
  }

  get #halted(): boolean {
    return this.#closed || this.#stopped;
  }

  #begin(): void {
    this.#start().catch((error: unknown) => this.#lost(error));
  }

  async #start(): Promise<void> {
    if (this.#starting || this.#halted) return;
    this.#starting = true;
    try {
      const loaded = await this.#refresh();
      if (loaded.kind !== "ready" || this.#halted) return;
      if (await this.#replay()) this.#connect();
    } finally {
      this.#starting = false;
    }
  }

  /** Replays everything after the cursor, so nothing missed while disconnected stays missing. */
  async #replay(): Promise<boolean> {
    for (;;) {
      const loaded = await this.#read(
        readOf(eventPage, this.#options.runId, this.#cursor),
      );
      if (this.#halted) return false;
      if (loaded.kind !== "ready") {
        this.#fail(loaded);
        return false;
      }
      const { page, events } = loaded.value;
      this.#add(events, page.gap);
      if (page.next_cursor <= this.#cursor) return true;
      this.#cursor = page.next_cursor;
    }
  }

  async #readSnapshot(): Promise<Loaded<RunWorkspace>> {
    const loaded = await this.#read(
      readOf(getRunWorkspace, this.#options.runId),
    );
    if (this.#halted) return loaded;
    if (loaded.kind === "ready") {
      this.#update({ load: withSnapshot(this.#view.load, loaded.value) });
    } else {
      this.#fail(loaded);
    }
    return loaded;
  }

  #read<T>(source: Read<T>): Promise<Loaded<T>> {
    const { fetch } = this.#options;
    return load(source, {
      signal: this.#controller.signal,
      ...(fetch === undefined ? {} : { fetch }),
    });
  }

  /** A refusal or a mismatch stops everything; an outage waits, then starts again. */
  #fail(failure: LoadFailure): void {
    if (this.#halted) return;
    this.#closeStream();
    this.#clearWait();
    if (stops(failure)) {
      this.#stopped = true;
      this.#update({
        load: withFailure(this.#view.load, failure, { attempt: 0, delayMs: 0 }),
      });
      return;
    }
    this.#failures += 1;
    const delayMs = retryDelay(this.#failures);
    this.#update({
      load: withFailure(this.#view.load, failure, {
        attempt: this.#failures,
        delayMs,
      }),
    });
    this.#cancelWait = this.#options.later(() => {
      this.#cancelWait = null;
      this.#begin();
    }, delayMs);
  }

  /** A failure no read classified, such as a bug: recorded by name and treated as an outage. */
  #lost(error: unknown): void {
    this.#options.report?.({
      event: "web.run_workspace_error",
      name: error instanceof Error ? error.name : typeof error,
    });
    this.#fail({ kind: "unavailable", status: null });
  }

  #connect(): void {
    this.#closeStream();
    this.#generation += 1;
    const generation = this.#generation;
    const current = () => generation === this.#generation && !this.#halted;
    this.#stream = this.#options.open(
      `${this.#base}/events/stream?after=${this.#cursor}`,
      {
        open: () => {
          if (current()) this.#setConnection("live");
        },
        // The browser's own retry would resume from a stale URL, so this uses the current cursor.
        error: () => {
          if (current()) this.#fail({ kind: "unavailable", status: null });
        },
        frame: (type, data) => {
          if (!current()) return;
          // A stream that delivered something is working, so the next drop starts the backoff over.
          this.#failures = 0;
          this.#frame(type, data);
        },
      },
    );
  }

  #frame(type: StreamFrame, data: unknown): void {
    switch (type) {
      case "run": {
        const event = parseEventFrame(data);
        if (event === null || event.sequence <= this.#cursor) return;
        this.#add([event], false);
        this.refresh();
        return;
      }
      case "live": {
        const event = parseEventFrame(data);
        const wanted = this.#options.streamWanted?.() ?? true;
        if (event?.payload.type !== "result.text.delta" || !wanted) return;
        this.#update({ live: withDelta(this.#view.live, event.payload) });
        return;
      }
      case "cursor": {
        // WRUN-06: a frame without a usable number is ignored, so the cursor never becomes NaN.
        const next = parseCursorFrame(data);
        if (next !== null) this.#cursor = Math.max(this.#cursor, next);
        return;
      }
      // SP-011: retained events can't fill the range, so the page marks the gap and reads the
      // authoritative snapshot. The StreamGap body says only where the range broke, which nothing
      // here uses, so it isn't parsed, and a malformed body can never hide a gap.
      case "gap":
        this.#update({ gap: true });
        this.refresh();
        return;
      case "end":
        this.#closeStream();
        this.#setConnection("ended");
        return;
    }
  }

  #add(incoming: readonly RunEvent[], gap: boolean): void {
    if (incoming.length === 0 && (!gap || this.#view.gap)) return;
    this.#update({
      events: mergeEvents(this.#view.events, incoming),
      gap: this.#view.gap || gap,
    });
  }

  #setConnection(connection: Connection): void {
    this.#update({ load: withConnection(this.#view.load, connection) });
  }

  #closeStream(): void {
    this.#stream?.close();
    this.#stream = null;
  }

  #clearWait(): void {
    this.#cancelWait?.();
    this.#cancelWait = null;
  }

  #update(patch: Partial<RunView>): void {
    if (this.#closed) return;
    this.#view = { ...this.#view, ...patch };
    this.#options.onChange(this.#view);
  }
}
