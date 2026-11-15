import type { ToolDescriptor } from "@autobots/api-client";

import { Badge } from "@/components/ui/badge";
import { AVAILABILITY_LABEL } from "@/lib/tools/text";

/** A tool's availability in words; the dot only repeats them (PRD-Tool-Catalog TS-01). */
export function AvailabilityBadge({ tool }: { tool: ToolDescriptor }) {
  const available = tool.availability === "available";
  return (
    <Badge
      variant={available ? "success" : "muted"}
      dot={available}
      data-availability={tool.availability}
    >
      {AVAILABILITY_LABEL[tool.availability]}
    </Badge>
  );
}
