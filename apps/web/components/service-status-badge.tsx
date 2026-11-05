import { CircleCheck, CircleAlert } from "lucide-react";

import type { ServiceStatus } from "@/lib/service-status";

// The meaning is in the words and icon, never the color alone.
export function ServiceStatusBadge({ status }: { status: ServiceStatus }) {
  const available = status === "available";
  const Icon = available ? CircleCheck : CircleAlert;
  return (
    <p
      role="status"
      data-status={status}
      className="bg-secondary text-secondary-foreground flex w-fit items-center gap-2 rounded-md px-2 py-1 text-sm"
    >
      <Icon aria-hidden="true" className="size-4" />
      {available
        ? "Python API: available"
        : "Python API: unavailable. Check that the local service is running."}
    </p>
  );
}
