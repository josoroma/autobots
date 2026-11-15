import type { RunWorkspace } from "@autobots/api-client";
import { CircleAlert, CircleCheck } from "lucide-react";
import { memo } from "react";

import { HairlineSection } from "@/components/ui/section";
import { unmetText } from "@/lib/runs/workspace-view";

/** Whether the result met its required artifacts and checks, once the run has been verified. */
export const VerificationSection = memo(function VerificationSection({
  verification,
}: {
  verification: RunWorkspace["verification"];
}) {
  if (verification === null) return null;
  return (
    <HairlineSection id="verification-heading" title="Verification">
      {verification.passed ? (
        <p
          data-verification="passed"
          className="flex items-start gap-2.5 text-sm leading-relaxed"
        >
          <CircleCheck
            aria-hidden="true"
            className="text-success-text mt-0.5 size-4 shrink-0"
          />
          {verification.checks === 0
            ? "An artifact was published. No content check was defined for this goal, so its content wasn't judged."
            : "Every required artifact and check passed."}
        </p>
      ) : (
        <div
          data-verification="failed"
          className="flex items-start gap-2.5 text-sm leading-relaxed"
        >
          <CircleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <div className="min-w-0 space-y-1">
            <p>Not everything required was met:</p>
            <ul className="marker:text-muted-foreground list-disc pl-5">
              {verification.unmet.map((item) => (
                <li key={item} className="break-words">
                  {unmetText(item)}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </HairlineSection>
  );
});
