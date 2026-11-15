import type { ModelPolicyState } from "@autobots/api-client";
import { Info, TriangleAlert } from "lucide-react";

import { INNER_BOX } from "@/components/ui/card";
import { differingRoles, summarizerDiffers } from "@/lib/model-roles";
import { cn } from "@/lib/utils";

/** Only what's saved is described, so the screen can't say a draft has taken effect. */
export function RoleEffect({ state }: { state: ModelPolicyState }) {
  const bindings = state.policy.bindings;
  const differing = differingRoles(bindings);
  return (
    <div
      data-field="role-effect"
      className={cn(INNER_BOX, "flex gap-3 px-3.5 text-body")}
    >
      <Info
        aria-hidden="true"
        className="text-muted-foreground mt-0.5 size-4 shrink-0"
      />
      <div className="min-w-0 space-y-1">
        <p>
          Only the executor&apos;s binding dispatches in this release. Other
          roles that differ from it don&apos;t take effect.
        </p>
        {differing.length === 0 ? (
          <p data-role-effect="same">
            Every role has the same binding as the executor now.
          </p>
        ) : (
          <p data-role-effect="differs">
            These differ from the executor, so they don&apos;t take effect:{" "}
            {differing.join(", ")}.
          </p>
        )}
        <p>
          A summarizer that differs pauses the run with route_not_bound, once
          the run needs compaction.
        </p>
        {summarizerDiffers(bindings) ? (
          <p data-role-effect="summarizer" className="font-medium">
            The summarizer differs here, so long runs will pause that way.
          </p>
        ) : null}
      </div>
    </div>
  );
}

/** A saved choice names a model that isn't offered, so new runs are refused until it changes. */
export function NotOfferedAlert() {
  return (
    <p
      data-field="not-offered"
      role="alert"
      className="border-destructive/40 dark:bg-destructive/10 flex gap-3 rounded-lg border px-3.5 py-3 text-body font-medium"
    >
      <TriangleAlert
        aria-hidden="true"
        className="text-destructive mt-0.5 size-4 shrink-0"
      />
      <span>
        A saved choice here names a model that isn&apos;t offered for new runs,
        so new runs are refused until you change it. Nothing replaces it for
        you.
      </span>
    </p>
  );
}
