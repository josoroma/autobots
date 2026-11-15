import type { RouteQualification } from "@autobots/api-client";
import { Route } from "lucide-react";

import {
  BOX_LIST,
  OperationsBox,
} from "@/components/operations/operations-box";
import { routeStatusText } from "@/lib/operations-text";

/** PRD-Studio OP-04: what the recorded live test found for each model route. */
export function RouteQualifications({
  routes,
}: {
  routes: readonly RouteQualification[];
}) {
  return (
    <OperationsBox
      id="routes-heading"
      icon={Route}
      heading="Route qualification"
    >
      <ul className={BOX_LIST}>
        {routes.map((route) => (
          <li
            key={route.profile}
            data-operations-route={route.profile}
            className="space-y-0.5 py-2.5"
          >
            <p className="font-mono text-meta font-medium break-all">
              {route.canonical_id}
            </p>
            <p>{routeStatusText(route)}</p>
            {route.limits === null ? null : (
              <p className="text-muted-foreground text-meta leading-relaxed">
                {route.limits}
              </p>
            )}
          </li>
        ))}
      </ul>
    </OperationsBox>
  );
}
