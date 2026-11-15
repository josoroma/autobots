"use client";

import {
  parseRunAccepted,
  parseSessionView,
  type RunRequest,
  type SessionView,
} from "@autobots/api-client";
import { Play } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AdmissionMessage } from "@/components/admission-message";
import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";
import { RunDisclosure } from "@/components/runs/disclosure/run-disclosure";
import { Card } from "@/components/ui/card";
import { Choice, Textarea } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/page-header";
import { csrfFetch } from "@/lib/csrf-fetch";
import { profileField } from "@/lib/model-profile";
import {
  ADMISSION_UNKNOWN,
  admissionRefusal,
  CHOICE_NOT_OFFERED,
} from "@/lib/run-admission";
import { type Outcome, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

const KEPT = "Your goal is kept.";

export function SessionPanel({ sessionId }: { sessionId: string }) {
  // One key until the outcome is known, and one press at a time (Decision 0027 D2).
  const admission = useSubmit();
  const [session, setSession] = useState<SessionView | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [goal, setGoal] = useState("");
  const [chosen, setChosen] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [problem, setProblem] = useState<{
    outcome: Outcome;
    text: string;
  } | null>(null);
  const [profile, setProfile] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
      cache: "no-store",
    })
      .then(async (reply) => {
        if (!active) return;
        if (!reply.ok) {
          setUnavailable(true);
          return;
        }
        setSession(parseSessionView(await reply.json()));
      })
      .catch(() => {
        if (active) setUnavailable(true);
      });
    return () => {
      active = false;
    };
  }, [sessionId]);

  async function run(): Promise<void> {
    if (session === null) return;
    setProblem(null);
    setRunId(null);
    const expertId =
      session.kind === "direct" ? session.options[0]?.expert_id : chosen;
    const choice = { refused: false };
    const result = await admission.submit({
      // Skipped while a request is held: that one is resent as it was.
      body: () => {
        const field = profileField(profile);
        choice.refused = field === null;
        return field === null
          ? null
          : JSON.stringify({
              goal_text: goal,
              session_id: session.id,
              expert_id: expertId ?? null,
              ...field,
            } satisfies RunRequest);
      },
      send: ({ key, body }) =>
        csrfFetch("/api/v1/runs", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseRunAccepted,
    });
    if (choice.refused)
      setProblem({ outcome: "refused", text: CHOICE_NOT_OFFERED });
    if (result === null || result.outcome === "changed") return;
    if (result.outcome === "accepted" && result.value !== null) {
      setRunId(result.value.run_id);
      return;
    }
    setProblem({
      outcome: result.outcome,
      text:
        result.outcome === "unknown"
          ? ADMISSION_UNKNOWN
          : withHeld(
              `${admissionRefusal(result.refusal, result.status)} ${KEPT}`,
              result.held,
            ),
    });
  }

  if (unavailable) {
    return (
      <p role="alert" data-state="unavailable" className="text-sm">
        That session is not available.
      </p>
    );
  }
  if (session === null) {
    return (
      <p role="status" className="text-muted-foreground text-sm">
        Loading this session.
      </p>
    );
  }
  const ready =
    goal.trim() !== "" && (session.kind === "direct" || chosen !== null);
  // While a request is held, its goal, Expert and model stay as sent (Decision 0027 D2).
  const held = admission.holding();
  return (
    <>
      <section aria-labelledby="options-heading" className="space-y-3">
        <SectionLabel id="options-heading">
          {session.kind === "direct"
            ? "Working with"
            : "This coordinator can route to"}
        </SectionLabel>
        <ul className="grid gap-3 @xl:grid-cols-2">
          {session.options.map((option) => (
            <li
              key={option.expert_id}
              data-option={option.name}
              className="bg-card text-card-foreground has-checked:border-primary/60 has-checked:ring-primary/15 flex gap-3 rounded-xl border p-4 has-checked:ring-3"
            >
              <span
                aria-hidden="true"
                className="bg-background grid size-9 shrink-0 place-items-center rounded-[10px] border font-serif text-base dark:border-transparent dark:bg-muted"
              >
                {option.name.trim().charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0 flex-1 space-y-1.5">
                {session.kind === "coordinator" ? (
                  <label className="flex items-start gap-2 text-[15px] font-semibold">
                    <Choice
                      type="radio"
                      name="expert"
                      checked={chosen === option.expert_id}
                      disabled={held}
                      onChange={() => setChosen(option.expert_id)}
                      className="mt-1 shrink-0"
                    />
                    <span>
                      {option.name}, version {option.version}
                    </span>
                  </label>
                ) : (
                  <p className="text-[15px] font-semibold">
                    {option.name}, version {option.version}
                  </p>
                )}
                <p data-field="tools" className="text-sm wrap-anywhere">
                  <span className="text-muted-foreground">Tools:</span>{" "}
                  <span className="font-mono text-[12.5px]">
                    {option.tools.length === 0
                      ? "none"
                      : option.tools.join(", ")}
                  </span>
                </p>
                <p data-field="models" className="text-sm wrap-anywhere">
                  <span className="text-muted-foreground">Models:</span>{" "}
                  <span className="font-mono text-[12.5px]">
                    {Object.keys(option.role_bindings).length === 0
                      ? "the workspace setting"
                      : Object.entries(option.role_bindings)
                          .map(([role, profile]) => `${role}: ${profile}`)
                          .join(", ")}
                  </span>
                </p>
              </div>
            </li>
          ))}
        </ul>
      </section>
      <Card aria-labelledby="work-heading" className="space-y-4 p-6">
        <h2
          id="work-heading"
          className="font-serif text-[22px] leading-tight font-normal tracking-tight"
        >
          New work
        </h2>
        <div className="space-y-1.5">
          <label htmlFor="session-goal" className="text-sm font-medium">
            Goal
          </label>
          <Textarea
            id="session-goal"
            rows={3}
            value={goal}
            readOnly={held}
            onChange={(event) => setGoal(event.target.value)}
          />
        </div>
        <RunDisclosure
          chosen={profile}
          // While held, the model shows as chosen with no picker (Decision 0027 D2).
          {...(held ? {} : { onChoose: setProfile })}
          roleOverrides={
            (session.kind === "direct"
              ? session.options[0]
              : session.options.find((option) => option.expert_id === chosen)
            )?.role_bindings
          }
        />
        {held ? <HeldNote /> : null}
        <div className="flex justify-end border-t pt-4">
          <Button
            onClick={() => void run()}
            disabled={!ready || admission.pending}
          >
            <Play aria-hidden="true" />
            Run
          </Button>
        </div>
        {runId === null ? null : (
          <AdmissionMessage outcome="accepted" className="text-sm">
            <span className="font-medium">Queued.</span>{" "}
            <Link href={`/runs/${runId}`} className="font-medium underline">
              Open this run
            </Link>
          </AdmissionMessage>
        )}
        {problem === null ? null : (
          <AdmissionMessage outcome={problem.outcome} className="text-sm">
            {problem.text}
          </AdmissionMessage>
        )}
      </Card>
    </>
  );
}
