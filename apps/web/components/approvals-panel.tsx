"use client";

import { parseApprovalList, type ApprovalView } from "@autobots/api-client";
import { ArrowUpRight, Check, Lock } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card, INNER_BOX } from "@/components/ui/card";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";

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
      <p
        role="alert"
        className="border-destructive/35 text-destructive rounded-lg border p-4 text-sm"
      >
        Approvals could not be loaded. Sign in, then try again.
      </p>
    );
  }
  if (approvals === null) {
    return (
      <p role="status" className="text-muted-foreground text-sm">
        Loading approvals.
      </p>
    );
  }
  return (
    <>
      {message === null ? null : (
        <p
          role="status"
          data-message="decision"
          className={cn(INNER_BOX, "text-sm")}
        >
          {message}
        </p>
      )}
      {approvals.length === 0 ? (
        <Card className="border-dashed">
          <p className="text-sm">Nothing is waiting for a decision.</p>
        </Card>
      ) : (
        approvals.map((approval) => (
          <Card
            key={approval.id}
            data-approval={approval.id}
            className="space-y-5 p-5 sm:p-6"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 space-y-2">
                <h2 className="font-serif text-[22px] leading-tight font-normal tracking-tight break-words">
                  {approval.tool_id}, version {approval.tool_version}
                </h2>
              </div>
              <Link
                href={`/runs/${approval.run_id}`}
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                  "w-fit shrink-0",
                )}
              >
                Open the run
                <ArrowUpRight aria-hidden="true" />
              </Link>
            </div>

            {/* The facts about this request, each with its own label. */}
            <dl className="grid overflow-hidden rounded-lg border text-[13px] sm:grid-cols-2">
              <Fact data-approval-requester="true" label="Requested by">
                {requesterText(approval)}
              </Fact>
              <Fact data-approval-reason="true" label="Why it's asking">
                {approval.policy_reason ??
                  "not recorded, as this request is older than that record."}
              </Fact>
              <Fact data-approval-scope="true" label="Scope when asked">
                {scopeText(approval)}
              </Fact>
              <Fact data-approval-policy="true" label="Policy version">
                {policyText(approval)}
              </Fact>
              <Fact
                label="Expires"
                colon={false}
                className="sm:col-span-2 sm:odd:border-r-0"
              >
                <span className="text-attention">
                  {new Date(approval.expires_at).toLocaleString()}.
                </span>
              </Fact>
            </dl>

            <div className="overflow-hidden rounded-xl border">
              <p className="border-b px-3.5 py-2.5 text-[12.5px] font-semibold dark:bg-muted/40">
                Exact request
              </p>
              <dl className="grid grid-cols-[6.5rem_minmax(0,1fr)] text-[13.5px]">
                <div data-approval-target="true" className="contents">
                  <dt className="text-muted-foreground border-b px-3.5 py-2.5 font-mono text-[12.5px]">
                    Target<span className="sr-only">:</span>
                  </dt>{" "}
                  <dd className="border-b py-2.5 pr-3.5 break-words">
                    {approval.resource_target ??
                      "not recorded. Read the exact request below."}
                  </dd>
                </div>
                <div className="contents">
                  <dt className="text-muted-foreground px-3.5 py-2.5 font-mono text-[12.5px]">
                    Effect<span className="sr-only">:</span>
                  </dt>{" "}
                  <dd className="py-2.5 pr-3.5">
                    {approval.operation_class.replaceAll("_", " ")}
                  </dd>
                </div>
              </dl>
              <pre
                tabIndex={0}
                className="max-h-96 overflow-auto border-t p-3.5 font-mono text-[13px] leading-relaxed break-words whitespace-pre-wrap dark:bg-muted/30"
              >
                {approval.arguments}
              </pre>
            </div>
            {approval.arguments_truncated ? (
              <p
                role="alert"
                className="border-destructive/35 text-destructive rounded-lg border p-3 text-sm font-medium"
              >
                {MESSAGES.approval_too_large}
              </p>
            ) : null}

            <p
              className={cn(INNER_BOX, "flex items-start gap-3 text-[13.5px]")}
            >
              <Lock
                aria-hidden="true"
                className="text-muted-foreground mt-0.5 size-4 shrink-0"
              />
              <span>
                <span className="font-semibold">
                  Approving releases only this exact request.
                </span>{" "}
                <span className="text-muted-foreground">
                  Rejecting lets the run replan or fail, and this request
                  won&apos;t run.
                </span>
              </span>
            </p>

            <div className="flex flex-wrap gap-2.5">
              <Button
                size="lg"
                onClick={() => void decide(approval, "approve")}
              >
                <Check aria-hidden="true" />
                Approve
              </Button>
              <Button
                size="lg"
                variant="outline"
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

// One labelled fact. The colon is for assistive technology and copied text; sighted readers see the label
// above the value.
function Fact({
  label,
  colon = true,
  className,
  children,
  ...props
}: {
  label: string;
  colon?: boolean;
  className?: string;
  children: ReactNode;
} & Record<`data-${string}`, string>) {
  return (
    <div
      className={cn(
        "border-b px-3.5 py-3 last:border-b-0 sm:odd:border-r",
        className,
      )}
      {...props}
    >
      <dt className="text-muted-foreground mb-0.5 text-xs">
        {label}
        {colon ? <span className="sr-only">:</span> : null}
      </dt>{" "}
      <dd className="break-words">{children}</dd>
    </div>
  );
}
