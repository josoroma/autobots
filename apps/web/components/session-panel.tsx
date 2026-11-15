"use client";

import {
  admitRun,
  type RunRequest,
  type SessionView,
} from "@autobots/api-client";
import { Play } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AdmissionMessage } from "@/components/admission-message";
import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";
import { RunDisclosure } from "@/components/runs/disclosure/run-disclosure";
import { Card, CardTitle, InitialTile } from "@/components/ui/card";
import { Choice, Field, Textarea } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/page-header";
import { writes } from "@/lib/api/browser";
import { initialOf } from "@/lib/experts/card";
import { profileField } from "@/lib/model-profile";
import {
  ADMISSION_UNKNOWN,
  admissionRefusal,
  CHOICE_NOT_OFFERED,
} from "@/lib/run-admission";
import { type Outcome, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

const KEPT = "Your goal is kept.";

// US-5.1: new work in a direct or coordinator session. The page reads the session on the server and
// passes it in (WCMP-07, R-67), so this keeps only the form.
export function SessionPanel({ session }: { session: SessionView }) {
  // One key until the outcome is known, and one press at a time (Decision 0027 D2).
  const admission = useSubmit<RunRequest>();
  const [goal, setGoal] = useState("");
  const [chosen, setChosen] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [problem, setProblem] = useState<{
    outcome: Outcome;
    text: string;
  } | null>(null);
  const [profile, setProfile] = useState("");

  async function run(): Promise<void> {
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
          : {
              goal_text: goal,
              session_id: session.id,
              expert_id: expertId ?? null,
              ...field,
            };
      },
      send: ({ key, body }) =>
        admitRun(writes, body, { "Idempotency-Key": key }),
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
            <Card
              as="li"
              key={option.expert_id}
              data-option={option.name}
              className="has-checked:border-primary/60 has-checked:ring-primary/15 flex gap-3 p-4 has-checked:ring-3"
            >
              <InitialTile
                initial={initialOf(option.name)}
                className="size-9 text-base"
              />
              <div className="min-w-0 flex-1 space-y-1.5">
                {session.kind === "coordinator" ? (
                  <label className="flex items-start gap-2 text-lead font-semibold">
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
                  <p className="text-lead font-semibold">
                    {option.name}, version {option.version}
                  </p>
                )}
                <p data-field="tools" className="text-sm wrap-anywhere">
                  <span className="text-muted-foreground">Tools:</span>{" "}
                  <span className="font-mono text-meta">
                    {option.tools.length === 0
                      ? "none"
                      : option.tools.join(", ")}
                  </span>
                </p>
                <p data-field="models" className="text-sm wrap-anywhere">
                  <span className="text-muted-foreground">Models:</span>{" "}
                  <span className="font-mono text-meta">
                    {Object.keys(option.role_bindings).length === 0
                      ? "the workspace setting"
                      : Object.entries(option.role_bindings)
                          .map(([role, profile]) => `${role}: ${profile}`)
                          .join(", ")}
                  </span>
                </p>
              </div>
            </Card>
          ))}
        </ul>
      </section>
      <Card aria-labelledby="work-heading" className="space-y-4 p-6">
        <CardTitle id="work-heading" size="display">
          New work
        </CardTitle>
        <Field id="session-goal" label="Goal">
          {(control) => (
            <Textarea
              {...control}
              rows={3}
              value={goal}
              readOnly={held}
              onChange={(event) => setGoal(event.target.value)}
            />
          )}
        </Field>
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
