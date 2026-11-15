import type { DelayedOccurrence, RestoreRecord } from "@autobots/api-client";
import { CalendarClock, History } from "lucide-react";

import {
  BOX_LIST,
  OperationsBox,
} from "@/components/operations/operations-box";
import { delayedText, restoreText } from "@/lib/operations-text";

const EMPTY = "text-muted-foreground text-sm";

/** PRD-Studio OP-04: routine occurrences recorded as delayed. */
export function DelayedSchedules({
  occurrences,
}: {
  occurrences: readonly DelayedOccurrence[];
}) {
  return (
    <OperationsBox
      id="delayed-heading"
      icon={CalendarClock}
      heading="Delayed schedules"
    >
      {occurrences.length === 0 ? (
        <p data-field="delayed" className={EMPTY}>
          No routine occurrence is recorded as delayed.
        </p>
      ) : (
        <ul data-field="delayed" className={BOX_LIST}>
          {occurrences.map((occurrence) => (
            <li
              key={`${occurrence.routine}-${occurrence.occurrence_time}`}
              className="py-2"
            >
              {delayedText(occurrence)}
            </li>
          ))}
        </ul>
      )}
    </OperationsBox>
  );
}

/** PRD-Studio OP-04: each recorded restore and whether it was verified. */
export function RestoreHistory({
  restores,
}: {
  restores: readonly RestoreRecord[];
}) {
  return (
    <OperationsBox
      id="restores-heading"
      icon={History}
      heading="Restore history"
    >
      {restores.length === 0 ? (
        <p data-field="restores" className={EMPTY}>
          No restore is recorded, so no backup here is known to restore.
        </p>
      ) : (
        <ul data-field="restores" className={BOX_LIST}>
          {restores.map((restore) => (
            <li key={`${restore.at}-${restore.result}`} className="py-2">
              {restoreText(restore)}
            </li>
          ))}
        </ul>
      )}
    </OperationsBox>
  );
}
