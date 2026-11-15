import type { LocalStatus, OperationCondition } from "@autobots/api-client";
import {
  Box,
  Database,
  HardDrive,
  Hourglass,
  ListChecks,
  ListOrdered,
  type LucideIcon,
  Pause,
  Server,
} from "lucide-react";

import {
  CHECK_LABEL,
  checkValue,
  conditionText,
  type CheckName,
} from "@/lib/operations-text";
import { StatusDot, type StatusDotTone } from "@/components/ui/status-dot";

// Decorative: each check's name and message carry its meaning.
const ICONS: Readonly<Record<CheckName, LucideIcon>> = {
  database: Database,
  schema: ListChecks,
  hold: Pause,
  adapter: Hourglass,
  storage: Box,
  disk: HardDrive,
  queue: ListOrdered,
  worker: Server,
};

// The dot only repeats the message beside it (Decision 0021 R4).
const DOTS: Readonly<Record<OperationCondition["state"], StatusDotTone>> = {
  ok: "success",
  degraded: "muted",
  unavailable: "danger",
};

function ConditionTile({
  condition,
  values,
}: {
  condition: OperationCondition;
  values: LocalStatus["values"];
}) {
  const Icon = ICONS[condition.name];
  const value = checkValue(condition.name, values);
  return (
    <li
      data-state={condition.state}
      className="bg-background min-h-24 space-y-1.5 px-4 py-3.5"
    >
      <p className="flex items-center gap-2 text-body font-semibold">
        <Icon
          aria-hidden="true"
          className="text-muted-foreground size-3.5 shrink-0"
        />
        {CHECK_LABEL[condition.name]}
        <span className="sr-only">: </span>
        <StatusDot tone={DOTS[condition.state]} className="ml-auto" />
      </p>
      <p className="text-muted-foreground text-meta leading-relaxed">
        {conditionText(condition.code)}
      </p>
      {value === null ? null : (
        <p
          data-field={`value-${condition.name}`}
          className="text-foreground text-meta break-words tabular-nums"
        >
          {value}
        </p>
      )}
    </li>
  );
}

/** PRD-Studio OP-02: one tile per check, with its sentence and its measured value (Decision 0022 D5). */
export function ConditionGrid({ status }: { status: LocalStatus }) {
  return (
    <ul
      data-field="checks"
      className="bg-border border-border grid gap-px overflow-hidden rounded-xl border sm:grid-cols-2 lg:grid-cols-4"
    >
      {status.conditions.map((condition) => (
        <ConditionTile
          key={condition.name}
          condition={condition}
          values={status.values}
        />
      ))}
    </ul>
  );
}
