"use client";

import { parseApprovalList, type ApprovalView } from "@autobots/api-client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { csrfFetch } from "@/lib/csrf-fetch";

const MESSAGES: Record<string, string> = {
  owner_required: "Only the workspace owner can decide.",
  approval_expired: "This request expired, so it was not approved.",
  approval_mismatch: "The request changed. Reload and review it again.",
  approval_too_large:
    "This request is too long to show whole, so it can't be approved. Reject it, or have it made smaller.",
  approval_already_decided: "This request was already decided.",
  approval_run_not_waiting:
    "The run isn't waiting for this decision. Resume it first.",
};

const NOT_RECORDED = "not recorded, as this request is older than that record.";

// Decision 0015: who started the run, and which agent proposed the call.
function requesterText(approval: ApprovalView): string {
  const requester = approval.requester;
  if (requester === null) {
    return NOT_RECORDED;
  }
  const person =
    requester.person_id === null
      ? "no person is recorded for this run"
      : requester.person_is_viewer
        ? "you started this run"
        : `member ${requester.person_id} started this run`;
  const agent =
    requester.agent === "coordinator"
      ? "the coordinator proposed it"
      : `Expert ${requester.expert_name === null ? requester.expert_id : `"${requester.expert_name}"`}, version ${requester.expert_version}, proposed it`;
  return `${person}, and ${agent}.`;
}

function scopeText(approval: ApprovalView): string {
  const scope = approval.scope_snapshot;
  if (scope === null) {
    return NOT_RECORDED;
  }
  const tools = Object.entries(scope.tools)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, version]) => `${name} version ${version}`);
  const paths = scope.paths.length === 0 ? "none" : scope.paths.join(", ");
  return `tools ${tools.length === 0 ? "none" : tools.join(", ")}; paths ${paths}.`;
}

function policyText(approval: ApprovalView): string {
  if (approval.policy_version === null) {
    return NOT_RECORDED;
  }
  const rule =
    approval.policy_rule === null
      ? ""
      : `, rule ${approval.policy_rule.replaceAll("_", " ")}`;
  return `${approval.policy_version}${rule}.`;
}

export function ApprovalsPanel() {
  const [approvals, setApprovals] = useState<readonly ApprovalView[] | null>(
    null,
  );
  const [failed, setFailed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    const reply = await fetch("/api/v1/approvals", { cache: "no-store" }).catch(
      () => null,
    );
    if (reply?.ok === true) {
      setApprovals(parseApprovalList(await reply.json()).approvals);
      setFailed(false);
    } else {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/approvals", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok)
          setApprovals(parseApprovalList(await reply.json()).approvals);
        else setFailed(true);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  async function decide(
    approval: ApprovalView,
    decision: "approve" | "reject",
  ): Promise<void> {
    setMessage(null);
    const reply = await csrfFetch(
      `/api/v1/approvals/${encodeURIComponent(approval.id)}/decision`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          decision,
          argument_hash: approval.argument_hash,
        }),
      },
    ).catch(() => null);
    if (reply?.ok === true) {
      setMessage(
        decision === "approve"
          ? "Approved. Only this exact request is released."
          : "Rejected. The run can replan or fail, and this request won't run.",
      );
    } else {
      const failure = (await reply?.json().catch(() => null)) as {
        code?: string;
      } | null;
      setMessage(
        MESSAGES[failure?.code ?? ""] ?? "That decision couldn't be saved.",
      );
    }
    await load();
  }

  if (failed) {
    return (
      <p role="alert" className="text-sm">
        Approvals could not be loaded. Sign in, then try again.
      </p>
    );
  }
  if (approvals === null) {
    return (
      <p role="status" className="text-sm">
        Loading approvals.
      </p>
    );
  }
  return (
    <>
      {message === null ? null : (
        <p role="status" data-message="decision" className="text-sm">
          {message}
        </p>
      )}
      {approvals.length === 0 ? (
        <p className="text-sm">Nothing is waiting for a decision.</p>
      ) : (
        approvals.map((approval) => (
          <Card
            key={approval.id}
            data-approval={approval.id}
            className="space-y-2"
          >
            <h2 className="text-lg font-medium">
              {approval.tool_id}, version {approval.tool_version}
            </h2>
            <p data-approval-reason="true" className="text-sm">
              Why it&apos;s asking:{" "}
              {approval.policy_reason ??
                "not recorded, as this request is older than that record."}
            </p>
            <p data-approval-target="true" className="text-sm break-words">
              Target:{" "}
              {approval.resource_target ??
                "not recorded. Read the exact request below."}
            </p>
            <p data-approval-requester="true" className="text-sm">
              Requested by: {requesterText(approval)}
            </p>
            <p data-approval-scope="true" className="text-sm break-words">
              Scope when asked: {scopeText(approval)}
            </p>
            <p data-approval-policy="true" className="text-sm">
              Policy version: {policyText(approval)}
            </p>
            <p className="text-sm">
              Effect: {approval.operation_class.replaceAll("_", " ")}
            </p>
            <pre
              tabIndex={0}
              className="bg-muted max-h-96 overflow-auto rounded-md p-3 text-sm break-words whitespace-pre-wrap"
            >
              {approval.arguments}
            </pre>
            {approval.arguments_truncated ? (
              <p role="alert" className="text-sm font-medium">
                {MESSAGES.approval_too_large}
              </p>
            ) : null}
            <p className="text-muted-foreground text-sm">
              Expires {new Date(approval.expires_at).toLocaleString()}.{" "}
              <Link href={`/runs/${approval.run_id}`} className="underline">
                Open the run
              </Link>
            </p>
            <div className="flex gap-3">
              <Button onClick={() => void decide(approval, "approve")}>
                Approve
              </Button>
              <Button
                variant="secondary"
                onClick={() => void decide(approval, "reject")}
              >
                Reject
              </Button>
            </div>
          </Card>
        ))
      )}
    </>
  );
}
