import type { ToolDescriptor, ToolGroupDescriptor } from "@autobots/api-client";
import { ShieldAlert } from "lucide-react";
import Link from "next/link";

import { AvailabilityBadge } from "@/components/tools/availability-badge";
import { GROUP_ICONS } from "@/components/tools/group-icons";
import { Badge } from "@/components/ui/badge";
import { IconTile } from "@/components/ui/card";
import { APPROVAL_TEXT, repairText, rowFacts } from "@/lib/tools/text";

/**
 * One tool's row: its link, facts, description, repair, availability and approval
 * (PRD-Tool-Catalog TS-01, TS-03).
 */
function ToolRow({
  tool,
  selected,
  href,
}: {
  tool: ToolDescriptor;
  selected: boolean;
  /** Opens the tool's dialog over this view. */
  href: string;
}) {
  const fix = repairText(tool);
  return (
    <li
      data-tool={tool.tool_id}
      className="border-border grid grid-cols-[30px_minmax(0,1fr)] items-start gap-x-3 gap-y-2 border-t px-3 py-2.5 sm:grid-cols-[30px_minmax(0,1fr)_auto]"
    >
      <IconTile
        icon={GROUP_ICONS[tool.group]}
        className="mt-0.5 size-[30px] rounded-lg"
      />
      <div className="min-w-0 space-y-1">
        <Link
          href={href}
          scroll={false}
          aria-current={selected ? "true" : undefined}
          className="text-body font-semibold underline-offset-4 hover:underline"
        >
          {tool.title}
        </Link>
        <p className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
          <code className="font-mono text-tag">
            {tool.tool_id} v{tool.version}
          </code>
          <span>{rowFacts(tool)}</span>
        </p>
        <p className="text-ui leading-relaxed">{tool.description}</p>
        {fix === null ? null : (
          <p className="text-ui" data-field="repair">
            {fix}
          </p>
        )}
      </div>
      <div className="col-start-2 flex flex-wrap items-center gap-1.5 sm:col-start-3 sm:flex-col sm:items-end">
        <AvailabilityBadge tool={tool} />
        {tool.approval === "never" ? null : (
          <Badge variant="attention">
            <ShieldAlert aria-hidden="true" />
            {APPROVAL_TEXT[tool.approval]}
          </Badge>
        )}
      </div>
    </li>
  );
}

/** One catalog group: its heading, how many tools show, its description and its rows. */
export function ToolGroupSection({
  group,
  tools,
  selected,
  panelHref,
}: {
  group: ToolGroupDescriptor;
  tools: readonly ToolDescriptor[];
  /** The tool whose dialog is open, or null. */
  selected: string | null;
  panelHref: (toolId: string) => string;
}) {
  return (
    <section aria-labelledby={`group-${group.group}`} data-group={group.group}>
      <div className="mb-1 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
        <h2 id={`group-${group.group}`} className="text-body font-semibold">
          {group.title}
        </h2>
        <span
          data-field="count"
          className="text-muted-foreground text-meta tabular-nums"
        >
          {tools.length} {tools.length === 1 ? "tool" : "tools"}
        </span>
        <p className="text-muted-foreground text-meta">{group.description}</p>
      </div>
      <ul>
        {tools.map((tool) => (
          <ToolRow
            key={tool.tool_id}
            tool={tool}
            selected={selected === tool.tool_id}
            href={panelHref(tool.tool_id)}
          />
        ))}
      </ul>
    </section>
  );
}
