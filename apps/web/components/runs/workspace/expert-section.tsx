import type { RunWorkspace } from "@autobots/api-client";
import { memo } from "react";

import { Section } from "@/components/runs/workspace/section";
import { expertModels, expertTools } from "@/lib/runs/workspace-view";

/** The Expert version this run was given. It can't use anything that isn't listed. */
export const ExpertSection = memo(function ExpertSection({
  expert,
}: {
  expert: RunWorkspace["expert"];
}) {
  if (expert === null) return null;
  return (
    <Section id="expert-heading" title="Expert">
      <div data-expert={expert.name} className="space-y-1.5 text-sm">
        <p className="break-words">
          {expert.name}, version {expert.version}
        </p>
        <p className="text-muted-foreground break-words">
          Tools:{" "}
          <span className="font-mono text-xs">{expertTools(expert.tools)}</span>
        </p>
        <p className="text-muted-foreground break-words">
          Models: {expertModels(expert.role_bindings)}
        </p>
      </div>
    </Section>
  );
});
