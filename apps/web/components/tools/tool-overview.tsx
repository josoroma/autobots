import type { ToolDescriptor } from "@autobots/api-client";
import {
  Clock,
  Globe,
  type LucideIcon,
  ShieldAlert,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import type { ReactNode } from "react";

import { AvailabilityBadge } from "@/components/tools/availability-badge";
import { GROUP_ICONS } from "@/components/tools/group-icons";
import { CardTitle, IconTile } from "@/components/ui/card";
import {
  APPROVAL_TEXT,
  costText,
  grantorText,
  limitsText,
  networkText,
  repairText,
} from "@/lib/tools/text";
import { cn } from "@/lib/utils";

/** The tool's icon, availability, title, description and repair (PRD-Tool-Catalog TS-01, TS-03). */
export function ToolHeader({ tool }: { tool: ToolDescriptor }) {
  const fix = repairText(tool);
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3">
        <IconTile icon={GROUP_ICONS[tool.group]} className="size-[34px]" />
        <div className="ml-auto">
          <AvailabilityBadge tool={tool} />
        </div>
      </div>
      <CardTitle
        id="tool-heading"
        size="display"
        className="tracking-[-0.015em]"
      >
        {tool.title}
      </CardTitle>
      <p className="text-muted-foreground text-body leading-relaxed">
        {tool.description}
      </p>
      {fix === null ? null : (
        <p className="text-sm" data-field="repair">
          {fix}
        </p>
      )}
    </div>
  );
}

/** What the tool does, when to use it and why (Decision 0026 G1). */
export function ToolGuide({ guide }: { guide: ToolDescriptor["guide"] }) {
  const terms = [
    ["What", guide.what],
    ["When", guide.when],
    ["Why", guide.why],
  ] as const;
  return (
    <dl data-field="guide" className="grid gap-3 border-t pt-4 sm:grid-cols-3">
      {terms.map(([term, text]) => (
        <div key={term} className="space-y-1">
          <dt className="text-muted-foreground text-xs font-semibold tracking-wide">
            {term}
          </dt>
          <dd
            data-guide={term.toLowerCase()}
            className="text-body leading-relaxed"
          >
            {text}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Fact({
  icon: Icon,
  term,
  className,
  children,
}: {
  icon: LucideIcon;
  term: string;
  className?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div className="border-border bg-background rounded-lg border px-3 py-2.5 text-ui">
      <dt className="text-muted-foreground mb-0.5 flex items-center gap-1.5 text-tag">
        <Icon aria-hidden="true" className="size-3.5 shrink-0" />
        {term}
      </dt>
      <dd className={cn(className)}>{children}</dd>
    </div>
  );
}

/** Where its calls go, what it costs, whether a person approves and its registered limits. */
export function ToolFacts({ tool }: { tool: ToolDescriptor }) {
  const approval = tool.approval !== "never";
  return (
    <dl className="grid gap-2 sm:grid-cols-2">
      <Fact icon={Globe} term="Network">
        {networkText(tool.network)}
      </Fact>
      <Fact icon={Wallet} term="Cost">
        {costText(tool)}
      </Fact>
      <Fact
        icon={approval ? ShieldAlert : ShieldCheck}
        term="Approval"
        className={approval ? "text-attention font-medium" : undefined}
      >
        {APPROVAL_TEXT[tool.approval]}
      </Fact>
      <Fact icon={Clock} term="Limits">
        {limitsText(tool.limits)}
      </Fact>
    </dl>
  );
}

/** What can grant the tool: goals, Experts, workflow nodes or a coordinator. */
export function GrantableTo({
  grantors,
}: {
  grantors: ToolDescriptor["grantable_to"];
}) {
  return (
    <dl className="space-y-2 border-t pt-4">
      <dt className="text-muted-foreground text-xs font-semibold tracking-wide">
        Can be granted by
      </dt>
      <dd>
        {grantors.length === 0 ? (
          <span className="text-sm">Nothing can grant it</span>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {grantors.map((item) => (
              <li
                key={item}
                className="border-border rounded-full border px-2.5 py-0.5 text-meta"
              >
                {grantorText(item)}
              </li>
            ))}
          </ul>
        )}
      </dd>
    </dl>
  );
}

/** The input and output schemas as registered, folded away by default. */
export function RawSchema({ tool }: { tool: ToolDescriptor }) {
  return (
    <details className="text-sm">
      <summary className="cursor-pointer font-semibold">JSON Schema</summary>
      <pre
        tabIndex={0}
        className="border-border bg-background mt-2 overflow-x-auto rounded-lg border px-3.5 py-3 font-mono text-xs leading-relaxed"
      >
        {JSON.stringify(
          { input: tool.input_schema, output: tool.output_schema },
          null,
          2,
        )}
      </pre>
    </details>
  );
}
