import type { RunWorkspace } from "@autobots/api-client";
import { memo } from "react";

import { Section } from "@/components/runs/workspace/section";

/** The goal as it was stored, and its criteria. */
export const GoalSection = memo(function GoalSection({
  objective,
  criteria,
}: {
  objective: RunWorkspace["objective"];
  criteria: RunWorkspace["criteria"];
}) {
  return (
    <Section id="goal-heading" title="Goal">
      <p className="font-document text-[17px] leading-relaxed break-words">
        {objective ?? "No goal is recorded."}
      </p>
      {criteria.length === 0 ? null : (
        <ul className="marker:text-muted-foreground list-disc space-y-1 pl-5 text-sm leading-relaxed">
          {criteria.map((criterion) => (
            <li key={criterion.id} className="break-words">
              {criterion.text}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
});
