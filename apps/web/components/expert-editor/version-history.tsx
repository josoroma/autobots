import type { ExpertView } from "@autobots/api-client";

import { Card } from "@/components/ui/card";
import { SectionLabel } from "@/components/ui/page-header";
import { versionToolsText } from "@/lib/experts/draft";

/** Every version of the Expert with what it grants. A saved version never changes. */
export function VersionHistory({
  versions,
}: {
  versions: ExpertView["versions"];
}) {
  return (
    <Card aria-labelledby="versions-heading" className="space-y-3">
      <SectionLabel id="versions-heading">Versions</SectionLabel>
      <ol className="text-sm">
        {versions.map((version) => (
          <li
            key={version.version}
            data-version={version.version}
            className="border-t py-2.5 wrap-anywhere first:border-t-0 first:pt-0"
          >
            <span className="font-medium">Version {version.version}</span>:{" "}
            <span className="text-muted-foreground font-mono text-xs">
              {versionToolsText(version.config)}
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
