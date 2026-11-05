"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { csrfFetch } from "@/lib/csrf-fetch";

// The draft and choice survive setup in this tab only. Opening or restoring them never starts anything:
// the one admission below happens only when Run is pressed. No credential is ever kept here.
const DRAFT_KEY = "autobots.draft";
const subscribe = () => () => undefined;

function storedDraft(): string {
  try {
    return window.sessionStorage.getItem(DRAFT_KEY) ?? "";
  } catch {
    return "";
  }
}

type Outcome =
  | "queued"
  | "credentials_required"
  | "credential_invalid"
  | "credential_unavailable"
  | "error";

export function GoalComposer() {
  const restored = useSyncExternalStore(subscribe, storedDraft, () => "");
  const [edited, setEdited] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const draft = edited ?? restored;

  function update(value: string): void {
    setEdited(value);
    try {
      window.sessionStorage.setItem(DRAFT_KEY, value);
    } catch {
      // Storage is unavailable, so the draft lasts only as long as this page.
    }
  }

  async function run(): Promise<void> {
    setOutcome(null);
    // One key per press, so a retried request admits one run and each new press is a new intent.
    const reply = await csrfFetch("/api/v1/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ goal_text: draft }),
    }).catch(() => null);
    if (reply?.ok === true) {
      setOutcome("queued");
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
    } | null;
    const known: Outcome[] = [
      "credentials_required",
      "credential_invalid",
      "credential_unavailable",
    ];
    setOutcome(known.find((code) => code === failure?.code) ?? "error");
  }

  return (
    <Card aria-labelledby="composer-heading" className="space-y-3">
      <h2 id="composer-heading" className="text-lg font-medium">
        New goal
      </h2>
      <label htmlFor="goal" className="text-sm font-medium">
        Goal
      </label>
      <textarea
        id="goal"
        value={draft}
        onChange={(event) => update(event.target.value)}
        rows={3}
        className="bg-background border-input block w-full rounded-md border px-3 py-2 text-sm"
      />
      <Button onClick={() => void run()} disabled={draft.trim() === ""}>
        Run
      </Button>
      {outcome === null ? null : (
        <p role="alert" data-outcome={outcome} className="text-sm">
          {outcome === "credentials_required" ? (
            <>
              Model-backed work needs an OpenRouter key. Your draft is kept.{" "}
              <Link href="/settings/models" className="font-medium underline">
                Set up OpenRouter
              </Link>
            </>
          ) : outcome === "credential_invalid" ? (
            <>
              The configured key was rejected. Your draft is kept.{" "}
              <Link href="/settings/models" className="font-medium underline">
                Fix it in settings
              </Link>
            </>
          ) : outcome === "credential_unavailable" ? (
            "Credential storage is unavailable, so model-backed work is blocked. Your draft is kept."
          ) : outcome === "queued" ? (
            "Your goal is queued. No worker runs it yet, so no model has been called."
          ) : (
            "That could not be checked. Sign in, then try again. Your draft is kept."
          )}
        </p>
      )}
    </Card>
  );
}
