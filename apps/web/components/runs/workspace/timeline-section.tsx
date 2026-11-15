import type { RunEvent } from "@autobots/api-client";
import { memo } from "react";

import { HairlineSection } from "@/components/ui/section";
import { describeEvent } from "@/lib/runs/run-events";

/** Stored events in order. After a retention gap it starts later, and says so (SP-011). */
export const TimelineSection = memo(function TimelineSection({
  events,
  gap,
}: {
  events: readonly RunEvent[];
  gap: boolean;
}) {
  return (
    <HairlineSection id="timeline-heading" title="Timeline">
      {gap ? (
        <p data-gap="true" className="text-sm">
          Earlier activity is no longer retained, so this starts later. The
          status above is current.
        </p>
      ) : null}
      <ol className="space-y-2 border-l pl-4 text-sm">
        {events.map((event) => (
          <li
            key={event.sequence}
            data-sequence={event.sequence}
            className="relative break-words"
          >
            <span
              aria-hidden="true"
              className="bg-muted-foreground absolute top-2 -left-[19.5px] size-1.5 rounded-full"
            />
            {describeEvent(event)}
          </li>
        ))}
      </ol>
    </HairlineSection>
  );
});
