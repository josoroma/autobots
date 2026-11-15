import type { ToolGrants } from "@autobots/api-client";
import Link from "next/link";

import { LoadEmpty, LoadState } from "@/components/ui/load-state";
import type { Resource } from "@/lib/use-resource";

const CHIP_LINK =
  "border-border inline-block rounded-full border px-2.5 py-0.5 underline-offset-4 hover:underline";

/**
 * PRD-Studio TL-02: Experts whose latest version grants this tool, and published workflows that
 * reach it, from a read the detail starts with its own.
 */
export function GrantedTo({
  toolId,
  grants,
}: {
  toolId: string;
  grants: Resource<ToolGrants>;
}) {
  const { state, pending, reload } = grants;
  return (
    <section
      aria-labelledby={`grants-${toolId}`}
      data-field="granted-to"
      className="space-y-2"
    >
      <h3 id={`grants-${toolId}`} className="text-sm font-semibold">
        Granted to
      </h3>
      {state.kind !== "ready" ? (
        <LoadState
          state={state}
          what="the Experts and workflows that grant it"
          onRetry={reload}
          pending={pending}
        />
      ) : state.value.experts.length === 0 &&
        state.value.workflows.length === 0 ? (
        <LoadEmpty>No Expert or published workflow grants it.</LoadEmpty>
      ) : (
        <ul className="flex flex-wrap gap-2 text-[12.5px]">
          {state.value.experts.map((item) => (
            <li key={item.id} data-granted-expert={item.id}>
              <Link href={`/experts/${item.id}`} className={CHIP_LINK}>
                Expert {item.name}, version {item.version}
              </Link>
            </li>
          ))}
          {state.value.workflows.map((item) => (
            <li key={item.id} data-granted-workflow={item.id}>
              <Link href={`/workflows/${item.id}`} className={CHIP_LINK}>
                Workflow {item.name}, version {item.version}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
