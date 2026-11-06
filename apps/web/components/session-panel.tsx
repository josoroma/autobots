"use client";

import { parseSessionView, type SessionView } from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { RunDisclosure } from "@/components/run-disclosure";
import { Card } from "@/components/ui/card";
import { Choice, Textarea } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";

export function SessionPanel({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<SessionView | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [goal, setGoal] = useState("");
  const [chosen, setChosen] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
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
    const reply = await csrfFetch("/api/v1/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({
        goal_text: goal,
        session_id: session.id,
        expert_id: expertId,
        ...(profile === "" ? {} : { run_profile: profile }),
      }),
    }).catch(() => null);
    if (reply?.ok === true) {
      setRunId(((await reply.json()) as { run_id: string }).run_id);
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
    } | null;
    setProblem(
      failure?.code === "credentials_required"
        ? "Model-backed work needs an OpenRouter key."
        : failure?.code === "model_not_offered"
          ? "A saved model choice isn't offered for new runs until it's qualified, so no run started. Your goal is kept."
          : reply?.status === 422
            ? "That request isn't approved, so no run started. Your goal is kept."
            : "That could not be started.",
    );
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
      <p role="status" className="text-sm">
        Loading this session.
      </p>
    );
  }
  const ready =
    goal.trim() !== "" && (session.kind === "direct" || chosen !== null);
  return (
    <>
      <Card aria-labelledby="options-heading" className="space-y-3">
        <h2 id="options-heading" className="text-lg font-medium">
          {session.kind === "direct"
            ? "Working with"
            : "This coordinator can route to"}
        </h2>
        <ul className="space-y-3 text-sm">
          {session.options.map((option) => (
            <li
              key={option.expert_id}
              data-option={option.name}
              className="space-y-1"
            >
              {session.kind === "coordinator" ? (
                <label className="flex items-center gap-2 font-medium">
                  <Choice
                    type="radio"
                    name="expert"
                    checked={chosen === option.expert_id}
                    onChange={() => setChosen(option.expert_id)}
                  />
                  {option.name}, version {option.version}
                </label>
              ) : (
                <p className="font-medium">
                  {option.name}, version {option.version}
                </p>
              )}
              <p data-field="tools">
                Tools:{" "}
                {option.tools.length === 0 ? "none" : option.tools.join(", ")}
              </p>
              <p data-field="models">
                Models:{" "}
                {Object.keys(option.role_bindings).length === 0
                  ? "the workspace setting"
                  : Object.entries(option.role_bindings)
                      .map(([role, profile]) => `${role}: ${profile}`)
                      .join(", ")}
              </p>
            </li>
          ))}
        </ul>
      </Card>
      <Card aria-labelledby="work-heading" className="space-y-3">
        <h2 id="work-heading" className="text-lg font-medium">
          New work
        </h2>
        <label htmlFor="session-goal" className="text-sm font-medium">
          Goal
        </label>
        <Textarea
          id="session-goal"
          rows={3}
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
        />
        <RunDisclosure
          chosen={profile}
          onChoose={setProfile}
          roleOverrides={
            (session.kind === "direct"
              ? session.options[0]
              : session.options.find((option) => option.expert_id === chosen)
            )?.role_bindings
          }
        />
        <Button onClick={() => void run()} disabled={!ready}>
          Run
        </Button>
        {runId === null ? null : (
          <p role="status" className="text-sm">
            Queued.{" "}
            <Link href={`/runs/${runId}`} className="font-medium underline">
              Open this run
            </Link>
          </p>
        )}
        {problem === null ? null : (
          <p role="alert" className="text-sm">
            {problem}
          </p>
        )}
      </Card>
    </>
  );
}
