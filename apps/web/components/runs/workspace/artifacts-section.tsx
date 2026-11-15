import type { RunWorkspace } from "@autobots/api-client";
import { FileText } from "lucide-react";
import { memo } from "react";

import { HairlineSection } from "@/components/ui/section";
import { artifactFacts } from "@/lib/runs/workspace-view";

/** The run's artifacts: a published one links to its download, and a missing one says so. */
export const ArtifactsSection = memo(function ArtifactsSection({
  artifacts,
}: {
  artifacts: RunWorkspace["artifacts"];
}) {
  return (
    <HairlineSection id="artifacts-heading" title="Artifacts">
      {artifacts.length === 0 ? (
        <p className="text-muted-foreground text-sm">No artifacts yet.</p>
      ) : (
        <ul className="divide-y text-sm">
          {artifacts.map((artifact) => (
            <li
              key={artifact.id}
              data-artifact-status={artifact.status}
              className="flex items-start gap-2.5 py-2 first:pt-0 last:pb-0"
            >
              <FileText
                aria-hidden="true"
                className="text-muted-foreground mt-0.5 size-4 shrink-0"
              />
              <span className="min-w-0 break-words">
                {artifact.status === "published" ? (
                  <a
                    href={`/api/v1/artifacts/${artifact.id}/download`}
                    className="font-mono text-ui font-medium underline underline-offset-4"
                  >
                    {artifact.name}
                  </a>
                ) : (
                  <span className="font-mono text-ui">
                    {`${artifact.name}: missing`}
                  </span>
                )}{" "}
                <span className="text-muted-foreground font-mono text-xs break-all">
                  {artifactFacts(artifact)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </HairlineSection>
  );
});
