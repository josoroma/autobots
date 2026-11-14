"use client";

import { parseRunList, type RunListItem } from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import {
  NOTIFY_CHANGED,
  notificationsSupported,
  notifyChosen,
} from "@/lib/notify";
import {
  newlyWaiting,
  pollDelay,
  WAITING_TITLE,
  type PollResult,
} from "@/lib/waiting";

type WaitingRead =
  | { result: "runs"; runs: RunListItem[] }
  | { result: Exclude<PollResult, "runs"> };

/** This workspace's runs that need the person. Never rejects: every outcome is a result. */
async function readWaiting(): Promise<WaitingRead> {
  try {
    const reply = await fetch("/api/v1/runs?group=needs_you", {
      cache: "no-store",
    });
    if (reply.ok) {
      return { result: "runs", runs: parseRunList(await reply.json()).runs };
    }
    await reply.text();
    return {
      result:
        reply.status === 401 || reply.status === 403 ? "signed_out" : "failed",
    };
  } catch {
    // No reply, a body that isn't JSON or one that has drifted from its contract.
    return { result: "failed" };
  }
}

// PRD-Studio SE-05: while the app is open, with the setting on and the browser's permission, a run
// that enters waiting_approval or waiting_input raises one browser notification. It reads this
// workspace's run list through the app's own API, and nothing is sent anywhere else. Runs already
// waiting when it starts are only noted, so it tells of what newly waits. Every poll schedules the
// next, slower when signed out and backing off after failures, and a restart's generation stops an
// older poll from scheduling a second loop (WCMP-06).
export function WaitingNotifier() {
  const router = useRouter();
  useEffect(() => {
    let seen: Set<string> | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let generation = 0;
    let failures = 0;
    let stopped = false;

    const allowed = () =>
      notifyChosen() &&
      notificationsSupported() &&
      Notification.permission === "granted";
    const current = (mine: number) => !stopped && mine === generation;

    function announce(run: RunListItem): void {
      const key = `${run.id}:${run.status}`;
      const note = new Notification(WAITING_TITLE[run.status] ?? "", {
        body: run.goal_summary === "" ? "Untitled run" : run.goal_summary,
        tag: key,
      });
      note.onclick = () => {
        window.focus();
        router.push(`/runs/${encodeURIComponent(run.id)}`);
      };
    }

    async function poll(mine: number): Promise<void> {
      timer = undefined;
      if (!current(mine)) return;
      // The setting or permission is off: nothing to watch until the setting changes.
      if (!allowed()) {
        seen = null;
        return;
      }
      const read = await readWaiting();
      if (!current(mine)) return;
      if (read.result === "runs") {
        const next = newlyWaiting(seen, read.runs);
        if (allowed()) next.fresh.forEach(announce);
        seen = next.seen;
      }
      // Signed out: whoever signs in next starts fresh, so their waiting runs are only noted (SE-05).
      if (read.result === "signed_out") seen = null;
      failures = read.result === "failed" ? failures + 1 : 0;
      timer = setTimeout(
        () => void poll(mine),
        pollDelay(read.result, failures),
      );
    }

    function restart(): void {
      generation += 1;
      if (timer !== undefined) clearTimeout(timer);
      timer = undefined;
      seen = null;
      failures = 0;
      void poll(generation);
    }

    window.addEventListener(NOTIFY_CHANGED, restart);
    void poll(generation);
    return () => {
      stopped = true;
      if (timer !== undefined) clearTimeout(timer);
      window.removeEventListener(NOTIFY_CHANGED, restart);
    };
  }, [router]);
  return null;
}
