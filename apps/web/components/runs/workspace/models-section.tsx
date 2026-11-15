import type { RunWorkspace } from "@autobots/api-client";
import { memo } from "react";

import { Section } from "@/components/runs/workspace/section";
import { BINDING_SOURCE_LABEL } from "@/lib/model-roles";

/** The role map this run froze at admission, which later settings don't change. */
export const ModelsSection = memo(function ModelsSection({
  roleMap,
  summarizerDiffers,
}: {
  roleMap: RunWorkspace["role_map"];
  summarizerDiffers: boolean;
}) {
  return (
    <Section id="models-heading" title="Models">
      {roleMap.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          This run has no frozen role map.
        </p>
      ) : (
        <div data-field="role-map" className="space-y-2.5 text-sm">
          <p className="text-muted-foreground text-[13px] leading-relaxed">
            What this run froze when it was admitted. Only the executor&apos;s
            binding dispatches in this release, and other roles that differ from
            it don&apos;t take effect.
          </p>
          {summarizerDiffers ? (
            <p
              data-role-map="summarizer"
              className="text-[13px] leading-relaxed"
            >
              The summarizer differs here, so this run pauses with
              route_not_bound if it needs compaction, and resuming won&apos;t
              clear that.
            </p>
          ) : null}
          <ul className="space-y-1.5">
            {roleMap.map((binding) => (
              <FrozenRole key={binding.role} binding={binding} />
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
});

/** One role's frozen binding, as requested, and which step of MP-01's order chose it. */
function FrozenRole({
  binding,
}: {
  binding: RunWorkspace["role_map"][number];
}) {
  return (
    <li className="text-[13px] leading-snug break-words">
      {binding.role}:{" "}
      <span className="font-mono text-xs break-all">
        {binding.canonical_id}
      </span>
      <span className="text-muted-foreground">, requested as </span>
      <span className="text-muted-foreground font-mono text-xs break-all">
        {binding.wire_id}
      </span>
      {binding.source === null ? null : (
        <span
          data-binding-source={binding.source}
          className="text-muted-foreground"
        >
          {" "}
          · {BINDING_SOURCE_LABEL[binding.source].toLowerCase()}
        </span>
      )}
    </li>
  );
}
