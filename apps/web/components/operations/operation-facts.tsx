import type { LocalStatus } from "@autobots/api-client";
import {
  Archive,
  Cloud,
  Layers,
  type LucideIcon,
  Network,
  Radio,
} from "lucide-react";
import type { ReactNode } from "react";

import {
  backupText,
  catalogTimeText,
  loopbackText,
  openrouterText,
  queueText,
  tracingText,
} from "@/lib/operations-text";

function FactRow({
  icon: Icon,
  field,
  children,
}: {
  icon: LucideIcon;
  field?: string;
  children: ReactNode;
}) {
  return (
    <p data-field={field} className="flex items-start gap-3 px-4 py-3">
      <Icon
        aria-hidden="true"
        className="text-muted-foreground mt-0.5 size-4 shrink-0"
      />
      <span>{children}</span>
    </p>
  );
}

/** PRD-Studio OP-04: tracing, the last backup, OpenRouter, the network and this workspace's jobs. */
export function OperationFacts({ status }: { status: LocalStatus }) {
  const fetchMs = status.values.catalog_fetch_ms;
  return (
    <section className="border-border divide-border divide-y rounded-xl border text-sm">
      <FactRow icon={Radio}>{tracingText(status.remote_tracing)}</FactRow>
      <FactRow icon={Archive}>{backupText(status.backup_age_hours)}</FactRow>
      <FactRow icon={Cloud} field="openrouter">
        {openrouterText(status.openrouter)}
        {fetchMs === null ? null : (
          <span data-field="catalog-time">{` ${catalogTimeText(fetchMs)}`}</span>
        )}
      </FactRow>
      <FactRow icon={Network} field="loopback">
        {loopbackText(status.values.loopback_only)}
      </FactRow>
      <FactRow icon={Layers}>{queueText(status.queue)}</FactRow>
    </section>
  );
}
