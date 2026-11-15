"use client";

import Link from "next/link";
import { Play } from "lucide-react";

import { AdmissionMessage } from "@/components/admission-message";
import { AttachmentField } from "@/components/composer/attachment-field";
import { PreviewChips } from "@/components/composer/preview-chips";
import { RunOptionChips } from "@/components/composer/run-option-chips";
import { useAttachments } from "@/components/composer/use-attachments";
import { useDraft } from "@/components/composer/use-draft";
import { useNewRunFocus } from "@/components/composer/use-new-run-focus";
import {
  type Said,
  useRunAdmission,
} from "@/components/composer/use-run-admission";
import { useRunOptions } from "@/components/composer/use-run-options";
import { useRunPreview } from "@/components/composer/use-run-preview";
import { HeldNote } from "@/components/held-note";
import { RunDisclosure } from "@/components/run-disclosure";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  INNER_BOX,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { budgetChoices } from "@/lib/budget";
import { cn } from "@/lib/utils";

/** What the card says after Run, with a link to an admitted run. */
function AdmissionNotice({ said }: { said: Said }) {
  return (
    <AdmissionMessage
      outcome={said.outcome}
      fix={said.kind === "queued" ? undefined : said.fix}
      data-outcome={said.kind}
      className={cn(INNER_BOX, "mx-5 mb-5 text-sm")}
    >
      {said.text}
      {said.kind === "queued" && said.runId !== null ? (
        <>
          {" "}
          <Link href={`/runs/${said.runId}`} className="font-medium underline">
            Open this run
          </Link>
        </>
      ) : null}
    </AdmissionMessage>
  );
}

/**
 * Home's composer (PRD-Studio HM-02, HM-03): a goal, the run's chips, what it would use, attached
 * files and Run. The one admission happens only when Run is pressed.
 */
export function GoalComposer() {
  useNewRunFocus();
  const draft = useDraft();
  const options = useRunOptions();
  const { preview, failed } = useRunPreview(options.profile, options.expertId);
  // The default until a choice is made, and never a value the server no longer offers.
  const budget = budgetChoices(preview?.budget ?? null, options.chosenBudget);
  const attachments = useAttachments();
  const admission = useRunAdmission(attachments.clear);
  // While a request is held, everything it sent stays as sent (Decision 0027 D2).
  const held = admission.held;

  return (
    <Card
      aria-labelledby="composer-heading"
      className="flex flex-col rounded-2xl p-0"
    >
      <CardHeader className="px-5 pt-5">
        <div className="min-w-0 flex-1 space-y-0.5">
          <CardTitle id="composer-heading" className="font-medium">
            New goal
          </CardTitle>
          <CardDescription>
            Describe the work, check what it would use, then press Run.
          </CardDescription>
        </div>
      </CardHeader>
      {/* Document order stays goal, chips (model, Expert, budget), what the run would use, attachments,
          Run, and the card reads top to bottom in that order, so Tab never climbs. */}
      <div className="flex flex-col gap-1 px-5 pt-4 pb-4">
        <label
          htmlFor="goal"
          className="text-muted-foreground text-xs font-medium"
        >
          Goal
        </label>
        <Textarea
          id="goal"
          value={draft.text}
          readOnly={held}
          onChange={(event) => draft.edit(event.target.value)}
          rows={4}
          className="min-h-28 resize-y text-base leading-relaxed"
        />
      </div>
      <RunOptionChips options={options} budget={budget} held={held} />
      <div className="flex flex-col gap-3 border-t px-5 py-4">
        <RunDisclosure
          chosen={options.profile}
          roleOverrides={options.roleOverrides}
          budgetMicroUsd={budget.budget}
        />
        <PreviewChips preview={preview} failed={failed} />
      </div>
      <AttachmentField attachments={attachments} held={held} />
      {held ? <HeldNote className="px-5 pt-2" /> : null}
      <div className="flex justify-end px-5 pt-2 pb-4">
        <Button
          onClick={() =>
            void admission.run({
              goal: draft.text,
              profile: options.profile,
              expertId: options.expertId,
              budget: budget.budget,
              files: attachments.files,
            })
          }
          disabled={
            draft.text.trim() === "" || budget.exhausted || admission.pending
          }
          size="lg"
          className="rounded-full px-5"
        >
          <Play aria-hidden="true" className="size-4" />
          Run
        </Button>
      </div>
      {admission.said === null ? null : (
        <AdmissionNotice said={admission.said} />
      )}
    </Card>
  );
}
