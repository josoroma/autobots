"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";

import { Play, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RunDisclosure } from "@/components/run-disclosure";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  INNER_BOX,
  IconTile,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";

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
  | "model_refused"
  | "error"
  | "model_not_offered";

export function GoalComposer() {
  const restored = useSyncExternalStore(subscribe, storedDraft, () => "");
  const [edited, setEdited] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [profile, setProfile] = useState("");
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
      body: JSON.stringify({
        goal_text: draft,
        ...(profile === "" ? {} : { run_profile: profile }),
      }),
    }).catch(() => null);
    if (reply?.ok === true) {
      const accepted = (await reply.json()) as { run_id: string };
      setRunId(accepted.run_id);
      setOutcome("queued");
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
    } | null;
    if (failure?.code === "model_not_offered") {
      setOutcome("model_not_offered");
      return;
    }
    if (reply?.status === 422) {
      setOutcome("model_refused");
      return;
    }
    const known: Outcome[] = [
      "credentials_required",
      "credential_invalid",
      "credential_unavailable",
    ];
    setOutcome(known.find((code) => code === failure?.code) ?? "error");
  }

  return (
    <Card aria-labelledby="composer-heading" className="flex flex-col gap-6">
      <CardHeader>
        <IconTile icon={Sparkles} />
        <div className="min-w-0 flex-1 space-y-1">
          <CardTitle id="composer-heading">New goal</CardTitle>
          <CardDescription>
            Describe the work, check what it would use, then press Run.
          </CardDescription>
        </div>
      </CardHeader>
      {/* Document order stays goal, model choice, Run, so Tab never skips back. On wide screens the
          disclosure sits beside the goal and Run sits at the bottom of the goal's column. */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="flex flex-col gap-2">
          <label htmlFor="goal" className="text-sm font-medium">
            Goal
          </label>
          <Textarea
            id="goal"
            value={draft}
            onChange={(event) => update(event.target.value)}
            rows={6}
            className="min-h-36 flex-1 resize-y"
          />
        </div>
        <div className="lg:row-span-2">
          <RunDisclosure chosen={profile} onChoose={setProfile} />
        </div>
        <Button
          onClick={() => void run()}
          disabled={draft.trim() === ""}
          className="w-full lg:self-end"
        >
          <Play aria-hidden="true" className="size-4" />
          Run
        </Button>
      </div>
      {outcome === null ? null : (
        <p
          role="alert"
          data-outcome={outcome}
          className={cn(INNER_BOX, "text-sm")}
        >
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
          ) : outcome === "model_not_offered" ? (
            <>
              A saved model choice isn&apos;t offered for new runs until
              it&apos;s qualified, so no run started. Your draft is kept.{" "}
              <Link href="/settings/models" className="font-medium underline">
                Change it in settings
              </Link>
            </>
          ) : outcome === "model_refused" ? (
            "That model or request isn't approved, so no run started. Your draft is kept."
          ) : outcome === "queued" ? (
            <>
              Your goal is queued.{" "}
              {runId === null ? null : (
                <Link href={`/runs/${runId}`} className="font-medium underline">
                  Open this run
                </Link>
              )}
            </>
          ) : (
            "That could not be checked. Sign in, then try again. Your draft is kept."
          )}
        </p>
      )}
    </Card>
  );
}
