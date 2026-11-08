import { CircleAlert, CircleCheck, CircleHelp } from "lucide-react";

import type { MemberReadiness } from "@autobots/api-client";
import { cn } from "@/lib/utils";

type Service = MemberReadiness["services"][number];

export const SERVICE_LABEL: Record<Service["name"], string> = {
  api: "Python API",
  worker: "Worker",
  database: "Database",
  openrouter: "OpenRouter",
};

// The words carry the meaning; the icon and its tone only repeat them (DS-03).
export function stateWords(service: Service): string {
  if (service.name === "openrouter") {
    return service.state === "ready"
      ? "authenticated"
      : service.state === "unknown"
        ? "unknown"
        : "not authenticated";
  }
  return service.state === "ready"
    ? "ready"
    : service.state === "unknown"
      ? "unknown"
      : "not ready";
}

// PRD-Studio SH-04: one line in the shell. It names the first service that isn't ready.
export function HealthLine({
  readiness,
}: {
  readiness: MemberReadiness | null;
}) {
  if (readiness === null) return null;
  const first = readiness.services.find((item) => item.state !== "ready");
  return (
    <p
      data-health={first === undefined ? "ready" : first.name}
      className="text-muted-foreground flex items-center gap-2 px-2 text-xs"
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          first === undefined ? "bg-success-text" : "bg-attention",
        )}
      />
      {first === undefined
        ? "All local services ready"
        : `${SERVICE_LABEL[first.name]} ${stateWords(first)}`}
    </p>
  );
}

// PRD-Studio HM-05: one chip per service, each in words.
export function ServiceChips({ readiness }: { readiness: MemberReadiness }) {
  return (
    <ul aria-label="Local services" className="flex flex-wrap gap-2">
      {readiness.services.map((service) => {
        const Icon =
          service.state === "ready"
            ? CircleCheck
            : service.state === "unknown"
              ? CircleHelp
              : CircleAlert;
        return (
          <li
            key={service.name}
            data-service={service.name}
            data-state={service.state}
            className="border-border flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"
          >
            <Icon
              aria-hidden="true"
              className={cn(
                "size-3.5 shrink-0",
                service.state === "ready"
                  ? "text-success-text"
                  : service.state === "unknown"
                    ? "text-muted-foreground"
                    : "text-attention",
              )}
            />
            <span className="font-medium">{SERVICE_LABEL[service.name]}</span>{" "}
            <span>{stateWords(service)}</span>
          </li>
        );
      })}
    </ul>
  );
}
