import type { RouteQualification } from "@autobots/api-client";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { QUALIFICATION_LABEL, QUALIFICATION_TONE } from "@/lib/provider-text";

function FactRow({
  term,
  field,
  className,
  children,
}: {
  term: string;
  field: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[6rem_minmax(0,1fr)] items-start gap-3">
      <dt className="text-muted-foreground">{term}</dt>
      <dd data-route-field={field} className={className}>
        {children}
      </dd>
    </div>
  );
}

function RouteCard({ route }: { route: RouteQualification }) {
  return (
    <Card
      data-route={route.profile}
      aria-label={route.canonical_id}
      className="flex min-w-0 flex-col gap-3 px-[18px] py-4"
    >
      <h3 className="font-mono text-meta font-medium break-all">
        {route.canonical_id}
      </h3>
      <dl className="border-border space-y-2 border-t pt-3 text-ui">
        <FactRow term="Status" field="status">
          <Badge
            variant={QUALIFICATION_TONE[route.status]}
            className="whitespace-normal"
          >
            {QUALIFICATION_LABEL[route.status]}
          </Badge>
        </FactRow>
        {route.qualified_on === null ? null : (
          <FactRow term="Tested on" field="date">
            {route.qualified_on}
          </FactRow>
        )}
        {route.configuration === null ? null : (
          <FactRow
            term="Configuration"
            field="configuration"
            className="break-words"
          >
            {route.configuration}
          </FactRow>
        )}
        {route.limits === null ? null : (
          <FactRow term="Limits" field="limits" className="break-words">
            {route.limits}
          </FactRow>
        )}
      </dl>
    </Card>
  );
}

/** What a live test of each route found, apart from the key's and the catalog's status. */
export function RouteQualifications({
  routes,
}: {
  routes: readonly RouteQualification[];
}) {
  return (
    <section
      aria-labelledby="qualification-heading"
      data-field="qualification"
      className="space-y-3"
    >
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <h2 id="qualification-heading" className="text-sm font-semibold">
          Live qualification
        </h2>
        <p className="text-muted-foreground text-meta">
          What a live test of each route found. A configured key does not mean a
          route was tested, and an available catalog does not either.
        </p>
      </div>
      <div className="grid gap-3.5 md:grid-cols-2 xl:grid-cols-3">
        {routes.map((route) => (
          <RouteCard key={route.profile} route={route} />
        ))}
      </div>
    </section>
  );
}
