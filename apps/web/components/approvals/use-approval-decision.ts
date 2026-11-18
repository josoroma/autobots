/**
 * Asks the service to decide one request, bound to the argument hash the person saw (PRD-Studio
 * AP-04). One key per decision until its outcome is known, scoped to the request, so a press for
 * the other decision while one is held sends nothing (Decision 0027 D2). A press while a decision is
 * in flight would send nothing either, so `pending` lets the screen wait. The message comes from the
 * status the service returned. Every decision except a `changed` press reads the list again through
 * `reload`, which reads the tab shown then, not the one the press came from (WTAP-04), and renders the
 * page again on the server, so the sidebar's pending count follows (XWEB-14, PRD-Studio SH-03).
 */
import {
  decideApproval,
  type ApprovalDecision as DecisionBody,
  type ApprovalView,
} from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { writes } from "@/lib/api/browser";
import type { Decision } from "@/lib/approval-shortcut";
import { decisionText } from "@/lib/approval-text";
import { useSubmit } from "@/lib/use-submit";

export interface ApprovalDecision {
  /** The newest decision's words, or null. */
  message: string | null;
  /** A decision is in flight, so the buttons and the shortcut wait until it settles. */
  pending: boolean;
  decide: (approval: ApprovalView, decision: Decision) => Promise<void>;
  clearMessage: () => void;
}

export function useApprovalDecision(reload: () => void): ApprovalDecision {
  const { submit, pending } = useSubmit<DecisionBody>();
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const clearMessage = useCallback(() => setMessage(null), []);

  const decide = useCallback(
    async (approval: ApprovalView, decision: Decision): Promise<void> => {
      setMessage(null);
      const result = await submit({
        body: () => ({ decision, argument_hash: approval.argument_hash }),
        send: ({ key, body }) =>
          decideApproval(writes, approval.id, body, { "Idempotency-Key": key }),
        scope: approval.id,
        choice: decision,
      });
      if (result === null) return;
      setMessage(decisionText(result));
      if (result.outcome === "changed") return;
      reload();
      router.refresh();
    },
    [submit, reload, router],
  );

  return { message, pending, decide, clearMessage };
}
