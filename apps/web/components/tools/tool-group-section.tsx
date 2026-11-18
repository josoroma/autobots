import type { ToolDescriptor, ToolGroupDescriptor } from "@autobots/api-client";
import { ShieldAlert } from "lucide-react";
import Link from "next/link";

import { AvailabilityBadge } from "@/components/tools/availability-badge";
import { GROUP_ICONS } from "@/components/tools/group-icons";
import { ToolSwitch } from "@/components/tools/tool-switch";
import type { SwitchWrites } from "@/components/tools/use-switch-writes";
import { Badge } from "@/components/ui/badge";
import { IconTile } from "@/components/ui/card";
import {
  APPROVAL_TEXT,
  groupSwitchText,
  repairText,
  rowFacts,
  switchText,
} from "@/lib/tools/text";

/** Who may change the switches, and how (Decision 0033 W4 and W5). */
export interface Switching {
  canSwitch: boolean;
  writes: SwitchWrites;
}

/**
 * One tool's row: its link, facts, description, repair, availability and approval
 * (PRD-Tool-Catalog TS-01, TS-03).
 */
function ToolRow({
  tool,
  selected,
  href,
  switching,
}: {
  tool: ToolDescriptor;
  selected: boolean;
  /** Opens the tool's dialog over this view. */
  href: string;
  switching: Switching;
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
        <RowSwitch tool={tool} switching={switching} />
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

/**
 * A tool's switch for the owner, or its state in words for a member (Decision 0033 W4). A tool its
 * group keeps off says so beside its own switch.
 */
function RowSwitch({
  tool,
  switching,
}: {
  tool: ToolDescriptor;
  switching: Switching;
}) {
  const state = tool.switch;
  const words = switchText(tool);
  if (!state || words === null) return null;
  if (!switching.canSwitch) {
    return (
      <span data-field="switch-state" className="text-meta">
        {words}
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <ToolSwitch
        label={`${tool.title} for this workspace`}
        on={state.enabled}
        disabled={switching.writes.pending}
        onToggle={(next) =>
          switching.writes.tool(tool.tool_id, next, state.version)
        }
      />
      {state.by === "group" ? (
        <span data-field="switch-state" className="text-meta">
          {words}
        </span>
      ) : null}
    </span>
  );
}

/** One catalog group: its heading, how many tools show, its description and its rows. */
export function ToolGroupSection({
  group,
  tools,
  selected,
  panelHref,
  switching,
}: {
  group: ToolGroupDescriptor;
  tools: readonly ToolDescriptor[];
  /** The tool whose dialog is open, or null. */
  selected: string | null;
  panelHref: (toolId: string) => string;
  switching: Switching;
}) {
  const groupSwitch = group.switch;
  const groupWords = groupSwitchText(group);
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
        {groupSwitch && groupWords !== null ? (
          <span className="ml-auto">
            {switching.canSwitch ? (
              <ToolSwitch
                label={`${group.title} group for this workspace`}
                on={groupSwitch.enabled}
                disabled={switching.writes.pending}
                onToggle={(next) =>
                  switching.writes.group(group.group, next, groupSwitch.version)
                }
              />
            ) : (
              <span data-field="group-switch-state" className="text-meta">
                {groupWords}
              </span>
            )}
          </span>
        ) : null}
      </div>
      <ul>
        {tools.map((tool) => (
          <ToolRow
            key={tool.tool_id}
            tool={tool}
            selected={selected === tool.tool_id}
            href={panelHref(tool.tool_id)}
            switching={switching}
          />
        ))}
      </ul>
    </section>
  );
}
