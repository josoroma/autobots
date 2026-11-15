"use client";

import { useSyncExternalStore } from "react";

// PRD-Studio HM-01 and Decision 0022 D14: by the workspace's own clock, morning 05:00–11:59,
// afternoon 12:00–17:59 and evening 18:00–04:59.
export function greetingFor(at: Date, timeZone: string): string {
  let hour: number;
  try {
    hour = Number(
      new Intl.DateTimeFormat("en-US", {
        hour: "numeric",
        hourCycle: "h23",
        timeZone,
      }).format(at),
    );
  } catch {
    hour = at.getUTCHours();
  }
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 18) return "Good afternoon";
  return "Good evening";
}

// Checked each minute, so a page left open moves into the next part of the day.
function subscribe(changed: () => void): () => void {
  const timer = window.setInterval(changed, 60_000);
  return () => window.clearInterval(timer);
}

export function HomeGreeting({
  name,
  timeZone,
}: {
  name: string;
  timeZone: string;
}) {
  // Read in the browser only, so the server's clock never decides it and hydration can't disagree.
  const greeting = useSyncExternalStore(
    subscribe,
    () => greetingFor(new Date(), timeZone),
    () => null,
  );
  return (
    <p
      data-field="greeting"
      className="text-muted-foreground min-h-[1.5em] text-lead"
    >
      {greeting === null ? null : (
        <>
          {greeting}, <span data-field="greeting-name">{name}</span>
        </>
      )}
    </p>
  );
}
