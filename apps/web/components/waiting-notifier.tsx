"use client";

import { parseRunList } from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import {
  NOTIFY_CHANGED,
  notificationsSupported,
  notifyChosen,
} from "@/lib/notify";

const EVERY_MS = 4_000;
const WAITING: Record<string, string> = {
  waiting_approval: "A run waits for your approval",
  waiting_input: "A run waits for your input",
};

// PRD-Studio SE-05: while the app is open, with the setting on and the browser's permission, a run
// that enters waiting_approval or waiting_input raises one browser notification. It reads this
// workspace's run list through the app's own API, and nothing is sent anywhere else. Runs already
// waiting when it starts are only noted, so it tells of what newly waits.
export function WaitingNotifier() {
  const router = useRouter();
  useEffect(() => {
    let seen: Set<string> | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const allowed = () =>
      notifyChosen() &&
      notificationsSupported() &&
      Notification.permission === "granted";

    async function poll(): Promise<void> {
      timer = undefined;
      if (stopped) return;
      if (!allowed()) {
        seen = null;
        return;
      }
      const reply = await fetch("/api/v1/runs?group=needs_you", {
        cache: "no-store",
      }).catch(() => null);
      if (stopped) return;
      if (reply?.ok === true) {
        const runs = parseRunList(await reply.json()).runs.filter(
          (run) => WAITING[run.status] !== undefined,
        );
        const now = new Set(runs.map((run) => `${run.id}:${run.status}`));
        if (seen !== null && allowed()) {
          for (const run of runs) {
            const key = `${run.id}:${run.status}`;
            if (seen.has(key)) continue;
            const note = new Notification(WAITING[run.status] ?? "", {
              body: run.goal_summary === "" ? "Untitled run" : run.goal_summary,
              tag: key,
            });
            note.onclick = () => {
              window.focus();
              router.push(`/runs/${encodeURIComponent(run.id)}`);
            };
          }
        }
        seen = now;
      } else if (reply !== null) {
        await reply.text();
        // Signed out or not a member: nothing to watch until the setting changes or the page loads.
        if (reply.status === 401 || reply.status === 403) return;
      }
      timer = setTimeout(() => void poll(), EVERY_MS);
    }

    function restart(): void {
      if (timer !== undefined) clearTimeout(timer);
      seen = null;
      void poll();
    }

    window.addEventListener(NOTIFY_CHANGED, restart);
    void poll();
    return () => {
      stopped = true;
      if (timer !== undefined) clearTimeout(timer);
      window.removeEventListener(NOTIFY_CHANGED, restart);
    };
  }, [router]);
  return null;
}
