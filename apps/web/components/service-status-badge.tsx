import { CircleAlert, CircleCheck, Cpu } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ServiceStatus } from "@/lib/service-status";

// The meaning is in the words and icon, never the color alone. The hidden colon keeps the sentence
// whole for assistive technology and for anything reading the text: "Python API: available".
// Decision 0021: a quiet row. The state icon carries the success or failure tone beside its words.
export function ServiceStatusBadge({ status }: { status: ServiceStatus }) {
  const available = status === "available";
  const Icon = available ? CircleCheck : CircleAlert;
  return (
    <p
      role="status"
      data-status={status}
      className="flex items-start gap-3 text-sm"
    >
      <Cpu
        aria-hidden="true"
        className="text-muted-foreground mt-0.5 size-4 shrink-0"
      />
      <span className="flex min-w-0 flex-1 flex-wrap items-start gap-x-3 gap-y-1">
        <span className="font-medium">
          Python API<span className="sr-only">:</span>
        </span>{" "}
        <span className="flex min-w-0 items-start gap-1.5">
          <Icon
            aria-hidden="true"
            data-status-icon
            className={cn(
              "mt-0.5 size-4 shrink-0",
              available ? "text-success-text" : "text-destructive",
            )}
          />
          {available ? (
            <span>available</span>
          ) : (
            <span>
              unavailable.{" "}
              <span className="text-muted-foreground">
                Check that the local service is running.
              </span>
            </span>
          )}
        </span>
      </span>
    </p>
  );
}
