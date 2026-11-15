import type { RunWorkspace } from "@autobots/api-client";
import { memo } from "react";

import { HairlineSection } from "@/components/ui/section";

/** The run this one is a part of, when it is a child run. */
export const ParentRunLink = memo(function ParentRunLink({
  parentRunId,
}: {
  parentRunId: string | null;
}) {
  if (parentRunId === null) return null;
  return (
    <p
      data-field="parent-run"
      className="text-muted-foreground border-t pt-6 text-sm"
    >
      This run is a part of{" "}
      <a
        href={`/runs/${parentRunId}`}
        className="text-foreground font-medium underline underline-offset-4"
      >
        its parent run
      </a>
      .
    </p>
  );
});

/** The child runs this one assigned to Experts, and how each went. */
export const AssignmentsSection = memo(function AssignmentsSection({
  assignments,
}: {
  assignments: RunWorkspace["assignments"];
}) {
  if (assignments.length === 0) return null;
  return (
    <HairlineSection id="assignments-heading" title="Assignments">
      <ul className="divide-y text-sm">
        {assignments.map((assignment) => (
          <li
            key={assignment.id}
            data-assignment={assignment.status}
            className="py-2 first:pt-0 last:pb-0"
          >
            <a
              href={`/runs/${assignment.child_run_id}`}
              className="font-medium underline underline-offset-4"
            >
              {assignment.expert}
            </a>
            <span className="text-muted-foreground">
              : {assignment.outcome ?? assignment.status}
            </span>
          </li>
        ))}
      </ul>
    </HairlineSection>
  );
});
