/**
 * Starting an execution of a published version, with its inputs and a budget from the server's
 * range (PRD-Studio WF-02, WF-05). Runs bind published versions only; the service owns the run.
 */
import { parseExecutionBinding, type WorkflowView } from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { budgetFor, type BudgetOffer } from "@/lib/budget";
import { csrfFetch } from "@/lib/csrf-fetch";
import { withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";
import { parseJsonText } from "@/lib/workflow-ir";

export interface VersionRun {
  /** The version a run binds, or null while none is published. */
  version: number | null;
  choose: (version: number) => void;
  inputs: string;
  setInputs: (inputs: string) => void;
  budget: number;
  chooseBudget: (budget: number) => void;
  run: () => Promise<void>;
  message: string | null;
  pending: boolean;
  /** A start is held, so what it sent stays as sent (Decision 0027 D2). */
  held: boolean;
}

/** A version picked while `latest` was the newest. Publishing again moves it to the new one. */
interface Choice {
  version: number;
  latest: number;
}

export function useVersionRun(
  workflow: WorkflowView,
  offer: BudgetOffer,
): VersionRun {
  // One key per press until its outcome is known (Decision 0027 D2): a double click or a lost reply
  // starts one execution, with one budget (WBLD-02).
  const executions = useSubmit();
  const router = useRouter();
  const [choice, setChoice] = useState<Choice | null>(null);
  const [inputs, setInputs] = useState("{}");
  const [chosenBudget, setChosenBudget] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const newest = workflow.versions.at(-1)?.version ?? null;
  const version =
    choice !== null && choice.latest === newest ? choice.version : newest;
  const budget = budgetFor(offer, chosenBudget);

  async function run(): Promise<void> {
    if (version === null) return;
    setMessage(null);
    const result = await executions.submit({
      body: () => {
        const values = parseJsonText(inputs);
        if (values === null) {
          setMessage("The inputs aren't valid JSON.");
          return null;
        }
        return JSON.stringify({
          version,
          inputs: values,
          ...(offer.kind === "unknown" || offer.choices.length === 0
            ? {}
            : { budget_micro_usd: budget }),
        });
      },
      send: ({ key, body }) =>
        csrfFetch(
          `/api/v1/workflows/${encodeURIComponent(workflow.id)}/executions`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": key,
            },
            body,
          },
        ),
      parse: parseExecutionBinding,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      router.push(`/workflow-executions/${result.value.id}`);
      return;
    }
    setMessage(
      result.outcome === "unknown"
        ? "The reply was lost, so it may have started. Pressing again won't start a second one."
        : withHeld(
            result.refusal?.message ?? "That could not be started.",
            result.held,
          ),
    );
  }

  return {
    version,
    choose: (picked) => setChoice({ version: picked, latest: newest ?? 0 }),
    inputs,
    setInputs,
    budget,
    chooseBudget: setChosenBudget,
    run,
    message,
    pending: executions.pending,
    held: executions.holding(),
  };
}
