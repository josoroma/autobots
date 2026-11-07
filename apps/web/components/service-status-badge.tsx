import { CircleAlert, CircleCheck, Cpu } from "lucide-react";

import { INNER_BOX } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ServiceStatus } from "@/lib/service-status";

// The meaning is in the words and icon, never the color alone. The hidden colon keeps the sentence
// whole for assistive technology and for anything reading the text: "Python API: available".
export function ServiceStatusBadge({ status }: { status: ServiceStatus }) {
  const available = status === "available";
  const Icon = available ? CircleCheck : CircleAlert;
  return (
    <p
      role="status"
      data-status={status}
      className={cn(INNER_BOX, "flex items-center gap-3 text-sm")}
    >
      <span
        aria-hidden="true"
        className="bg-card grid size-9 shrink-0 place-items-center rounded-xl border"
      >
        <Cpu className="size-4" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="font-medium">
          Python API<span className="sr-only">:</span>
        </span>{" "}
        <span className="flex items-start gap-1.5">
          <Icon
            aria-hidden="true"
            data-status-icon
            className={cn(
              "mt-0.5 size-4 shrink-0",
              available ? "text-foreground" : "text-destructive",
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
