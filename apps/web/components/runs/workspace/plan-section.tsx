import type { RunWorkspace } from "@autobots/api-client";
import { CircleCheck, CircleDashed } from "lucide-react";
import { memo } from "react";

import { Section } from "@/components/runs/workspace/section";
import { planNote, taskProgress } from "@/lib/runs/workspace-view";

/** The current plan's version, why it was revised, and each task's state and evidence. */
export const PlanSection = memo(function PlanSection({
  plan,
}: {
  plan: RunWorkspace["plan"];
}) {
  return (
    <Section id="plan-heading" title="Plan">
      {plan === null ? (
        <p className="text-muted-foreground text-sm">No plan yet.</p>
      ) : (
        <>
          <p className="text-muted-foreground text-xs">{planNote(plan)}</p>
          <ul className="bg-card divide-y rounded-xl border text-sm">
            {plan.tasks.map((task) => (
              <li
                key={task.id}
                data-task-status={task.status}
                className="flex items-start gap-3 px-4 py-3"
              >
                {task.status === "complete" ? (
                  <CircleCheck
                    aria-hidden="true"
                    className="text-success-text mt-0.5 size-4 shrink-0"
                  />
                ) : (
                  <CircleDashed
                    aria-hidden="true"
                    className="text-muted-foreground mt-0.5 size-4 shrink-0"
                  />
                )}
                <span className="min-w-0 leading-relaxed break-words">
                  <span className="font-medium">{task.title}</span>:{" "}
                  <span className="text-muted-foreground">
                    {taskProgress(task)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
});
