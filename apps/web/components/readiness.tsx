import type { MemberReadiness } from "@autobots/api-client";
import {
  CircleAlert,
  CircleCheck,
  CircleHelp,
  type LucideIcon,
} from "lucide-react";

import {
  healthLine,
  READINESS,
  SERVICE_LABEL,
  stateWords,
  type Service,
  type Tone,
} from "@/lib/readiness";
import { cn } from "@/lib/utils";

// Decorative: the words beside each icon and dot carry the meaning; they only repeat it (DS-03).
const ICON: Readonly<Record<Service["state"], LucideIcon>> = {
  ready: CircleCheck,
  not_ready: CircleAlert,
  unknown: CircleHelp,
};
const TEXT: Readonly<Record<Tone, string>> = {
  success: "text-success-text",
  attention: "text-attention",
  muted: "text-muted-foreground",
};
const DOT: Readonly<Record<Tone, string>> = {
  success: "bg-success-text",
  attention: "bg-attention",
  muted: "bg-muted-foreground",
};

// PRD-Studio SH-04: one line in the shell. It names the first service that isn't ready.
export function HealthLine({
  readiness,
}: {
  readiness: MemberReadiness | null;
}) {
  if (readiness === null) return null;
  const line = healthLine(readiness);
  return (
    <p
      data-health={line.field}
      className="text-muted-foreground flex items-center gap-2 px-2 text-xs"
    >
      <span
        aria-hidden="true"
        className={cn("size-1.5 shrink-0 rounded-full", DOT[line.tone])}
      />
      {line.words}
    </p>
  );
}

// PRD-Studio HM-05: one chip per service, each in words.
export function ServiceChips({ readiness }: { readiness: MemberReadiness }) {
  return (
    <ul aria-label="Local services" className="flex flex-wrap gap-2">
      {readiness.services.map((service) => {
        const Icon = ICON[service.state];
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
                TEXT[READINESS[service.state].tone],
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
