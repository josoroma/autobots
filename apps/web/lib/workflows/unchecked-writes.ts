/**
 * The routes of the workflow writes whose body holds JSON a person typed: a graph to validate,
 * publish or save as the draft, and an execution's inputs, which only the service validates
 * (PRD-Studio WF-02). Their generated operations can't take an unchecked value, so these name the
 * routes `writeAsTyped` sends to, and a unit test checks each against its generated operation
 * (R-48). Pure and JSX-free.
 */
import type { TypedRoute } from "../api/browser.ts";

function workflow(workflowId: string): string {
  return `/v1/workflows/${encodeURIComponent(workflowId)}`;
}

/** validateWorkflow's route. */
export const VALIDATE_ROUTE: TypedRoute = {
  method: "POST",
  path: "/v1/workflows/validate",
};

/** publishWorkflowVersion's route. */
export function publishRoute(workflowId: string): TypedRoute {
  return { method: "POST", path: `${workflow(workflowId)}/versions` };
}

/** saveWorkflowDraft's route. */
export function draftRoute(workflowId: string): TypedRoute {
  return { method: "PUT", path: `${workflow(workflowId)}/draft` };
}

/** createWorkflowExecution's route. */
export function executionRoute(workflowId: string): TypedRoute {
  return { method: "POST", path: `${workflow(workflowId)}/executions` };
}
