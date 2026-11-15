import type { ProviderStatus } from "@autobots/api-client";
import { Cpu } from "lucide-react";
import type { ReactNode } from "react";

import { IconTile } from "@/components/ui/card";
import {
  AUTH_LABEL,
  AUTH_TONE,
  CATALOG_LABEL,
  CATALOG_TONE,
  SOURCE_LABEL,
  type Tone,
} from "@/lib/provider-text";
import { cn } from "@/lib/utils";

// Decorative dots beside each status. The words carry the meaning; the dot only repeats it.
const DOT: Readonly<Record<Tone, string>> = {
  ok: "bg-success-text",
  bad: "bg-destructive",
  idle: "border-muted-foreground border-[1.5px]",
};

function StatusDot({ tone }: { tone: Tone }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "mt-[7px] inline-block size-[7px] shrink-0 rounded-full",
        DOT[tone],
      )}
    />
  );
}

function Cell({
  label,
  field,
  className,
  children,
}: {
  label: string;
  field: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 px-[18px] py-3.5">
      <dt className="text-muted-foreground mb-[3px] text-xs">{label}</dt>
      <dd data-field={field} className={className}>
        {children}
      </dd>
    </div>
  );
}

/** The provider's name, then its source, authentication, catalog and stored version, in words. */
export function ConnectionBar({ status }: { status: ProviderStatus }) {
  return (
    <div className="flex flex-col lg:flex-row">
      <div className="flex items-center gap-3 px-[18px] py-3.5 lg:w-48 lg:shrink-0">
        <IconTile icon={Cpu} />
        <h2 id="openrouter-heading" className="text-sm font-semibold">
          OpenRouter
        </h2>
      </div>
      <dl className="divide-border border-border grid min-w-0 flex-1 divide-y border-t text-[13px] lg:auto-cols-fr lg:grid-flow-col lg:divide-x lg:divide-y-0 lg:border-t-0 lg:border-l">
        <Cell label="Source" field="source">
          {SOURCE_LABEL[status.source]}
        </Cell>
        <Cell label="Authentication" field="auth" className="flex gap-2">
          <StatusDot tone={AUTH_TONE[status.auth_status]} />
          {AUTH_LABEL[status.auth_status]}
        </Cell>
        <Cell label="Catalog" field="catalog" className="flex gap-2">
          <StatusDot tone={CATALOG_TONE[status.catalog_status]} />
          {CATALOG_LABEL[status.catalog_status]}
        </Cell>
        {status.credential_version === null ? null : (
          <Cell label="Stored version" field="version" className="tabular-nums">
            {status.credential_version}
          </Cell>
        )}
      </dl>
    </div>
  );
}
