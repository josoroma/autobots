"use client";

import {
  parseApprovalList,
  type ApprovalList,
  type ApprovalView,
} from "@autobots/api-client";
import { ArrowUpRight, Check, Lock } from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

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

const OUTCOME: Record<string, string> = {
  approved: "Approved",
  rejected: "Rejected",
  expired: "Expired, so it was not approved",
  withdrawn: "Withdrawn",
};

type Tab = "waiting" | "decided";

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

function relative(iso: string, now: number): string {
  const minutes = Math.round((new Date(iso).getTime() - now) / 60_000);
  const size = Math.abs(minutes);
  const amount =
    size < 60
      ? `${size} min`
      : size < 60 * 48
        ? `${Math.round(size / 60)} h`
        : `${Math.round(size / 1440)} d`;
  return minutes >= 0 ? `in ${amount}` : `${amount} ago`;
}

function decidedText(approval: ApprovalView): string {
  const outcome = OUTCOME[approval.status] ?? approval.status;
  const who =
    approval.decided_by === "you"
      ? " by you"
      : approval.decided_by === "member"
        ? ` by ${approval.decided_by_name ?? "a workspace member"}`
        : "";
  const when =
    approval.decided_at === null
      ? ""
      : ` at ${new Date(approval.decided_at).toLocaleString()}`;
  return `${outcome}${who}${when}.`;
}

function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
  );
}

// PRD-Studio AP-01 to AP-04: Waiting and Decided with counts, the list beside the selected request,
// J and K to move, and ⌘↵ or ⌘⌫ pressed twice within 2 s to decide.
export function ApprovalsPanel() {
  const [tab, setTab] = useState<Tab>("waiting");
  const [list, setList] = useState<ApprovalList | null>(null);
  const [counts, setCounts] = useState<ApprovalList["counts"] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [armed, setArmed] = useState<{
    decision: "approve" | "reject";
    until: number;
  } | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async (which: Tab): Promise<void> => {
    const url =
      which === "waiting"
        ? "/api/v1/approvals"
        : "/api/v1/approvals?status=decided";
    const reply = await fetch(url, { cache: "no-store" }).catch(() => null);
    if (reply?.ok === true) {
      const parsed = parseApprovalList(await reply.json());
      setList(parsed);
      setCounts(parsed.counts);
      setSelected((current) =>
        parsed.approvals.some((item) => item.id === current)
          ? current
          : (parsed.approvals[0]?.id ?? null),
      );
      setFailed(false);
    } else {
      setFailed(true);
    }
    setNow(Date.now());
  }, []);

  useEffect(() => {
    let active = true;
    const url =
      tab === "waiting"
        ? "/api/v1/approvals"
        : "/api/v1/approvals?status=decided";
    fetch(url, { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) {
          const parsed = parseApprovalList(await reply.json());
          setList(parsed);
          setCounts(parsed.counts);
          setCounts(parsed.counts);
          setSelected((current) =>
            parsed.approvals.some((item) => item.id === current)
              ? current
              : (parsed.approvals[0]?.id ?? null),
          );
          setFailed(false);
          setNow(Date.now());
        } else setFailed(true);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [tab]);

  const approvals = useMemo(() => list?.approvals ?? [], [list]);
  const current = approvals.find((item) => item.id === selected) ?? null;

  const decide = useCallback(
    async (approval: ApprovalView, decision: "approve" | "reject") => {
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
      await load(tab);
    },
    [load, tab],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent): void {
      if (typing(event.target)) return;
      if (!event.metaKey && !event.ctrlKey && !event.altKey) {
        // Arrows move too while focus is in the list, which is one tab stop on the selected request.
        const inList =
          event.target instanceof HTMLElement &&
          event.target.hasAttribute("data-approval-item");
        const down = event.key === "j" || (inList && event.key === "ArrowDown");
        const up = event.key === "k" || (inList && event.key === "ArrowUp");
        if (!down && !up) return;
        const index = approvals.findIndex((item) => item.id === selected);
        const next =
          approvals[
            Math.max(0, Math.min(approvals.length - 1, index + (down ? 1 : -1)))
          ];
        if (next !== undefined) {
          event.preventDefault();
          setSelected(next.id);
          setArmed(null);
          if (inList)
            requestAnimationFrame(() =>
              document
                .querySelector<HTMLElement>(`[data-approval-item="${next.id}"]`)
                ?.focus(),
            );
        }
        return;
      }
      const decision =
        event.key === "Enter"
          ? "approve"
          : event.key === "Backspace"
            ? "reject"
            : null;
      if (decision === null || current === null || tab !== "waiting") return;
      event.preventDefault();
      if (decision === "approve" && current.arguments_truncated) {
        setAnnouncement(MESSAGES.approval_too_large ?? "");
        return;
      }
      if (
        armed !== null &&
        armed.decision === decision &&
        Date.now() <= armed.until
      ) {
        setArmed(null);
        setAnnouncement("");
        void decide(current, decision);
        return;
      }
      setArmed({ decision, until: Date.now() + 2_000 });
      setAnnouncement(
        `Press ${decision === "approve" ? "⌘↵" : "⌘⌫"} again within 2 seconds to ${decision} ${current.tool_id}, version ${current.tool_version}.`,
      );
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [approvals, selected, current, tab, armed, decide]);

  useEffect(() => {
    if (armed === null) return;
    const timer = setTimeout(
      () => {
        setArmed(null);
        setAnnouncement("Nothing was decided.");
      },
      Math.max(0, armed.until - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [armed]);

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
  if (counts === null) {
    return (
      <p role="status" className="text-muted-foreground text-sm">
        Loading approvals.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <div
        role="group"
        aria-label="Requests"
        className="bg-muted/60 inline-flex w-fit gap-0.5 rounded-lg p-[3px]"
      >
        {(
          [
            ["waiting", "Waiting", counts.waiting],
            ["decided", "Decided", counts.decided],
          ] as const
        ).map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            data-tab={id}
            aria-pressed={tab === id}
            onClick={() => {
              if (id === tab) return;
              // A stale list from the other tab is never shown while the new one loads.
              setList(null);
              setTab(id);
              setMessage(null);
              setArmed(null);
            }}
            className={cn(
              "text-foreground/80 inline-flex h-7 items-center gap-1.5 rounded-md border border-transparent px-3 text-[13px]",
              tab === id &&
                "bg-background text-foreground border-border font-medium dark:bg-accent",
            )}
          >
            {label} <span className="tabular-nums">{count}</span>
          </button>
        ))}
      </div>
      {message === null ? null : (
        <p
          role="status"
          data-message="decision"
          className={cn(INNER_BOX, "text-sm")}
        >
          {message}
        </p>
      )}
      <p
        aria-live="polite"
        data-message="shortcut"
        className="text-muted-foreground min-h-5 text-[12.5px]"
      >
        {announcement}
      </p>
      {list === null ? (
        <p role="status" className="text-muted-foreground text-sm">
          Loading approvals.
        </p>
      ) : approvals.length === 0 ? (
        <Card className="border-dashed">
          <p className="text-sm">
            {tab === "waiting"
              ? "Nothing is waiting for a decision."
              : "Nothing has been decided yet."}
          </p>
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <ul
            aria-label={
              tab === "waiting" ? "Waiting requests" : "Decided requests"
            }
            className="divide-border h-fit divide-y overflow-hidden rounded-xl border"
          >
            {approvals.map((approval) => (
              <li key={approval.id}>
                <button
                  type="button"
                  data-approval-item={approval.id}
                  aria-current={approval.id === selected ? "true" : undefined}
                  tabIndex={approval.id === selected ? 0 : -1}
                  onClick={() => {
                    setSelected(approval.id);
                    setArmed(null);
                  }}
                  className={cn(
                    "hover:bg-accent/60 block w-full border-l-2 border-transparent px-3.5 py-3 text-left text-[13.5px]",
                    approval.id === selected &&
                      "border-l-attention bg-background font-medium dark:bg-accent",
                  )}
                >
                  <span className="block break-words">
                    {approval.tool_id}, version {approval.tool_version}
                  </span>
                  <span className="text-muted-foreground block text-xs break-words">
                    {approval.run_goal ?? "Run goal not recorded"}
                  </span>
                  <span className="text-muted-foreground block text-xs">
                    {tab === "waiting"
                      ? `Expires ${relative(approval.expires_at, now)}`
                      : (OUTCOME[approval.status] ?? approval.status)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {current === null ? null : (
            <ApprovalDetail
              key={current.id}
              approval={current}
              now={now}
              waiting={tab === "waiting"}
              onDecide={(decision) => void decide(current, decision)}
            />
          )}
        </div>
      )}
    </div>
  );
}

function ApprovalDetail({
  approval,
  now,
  waiting,
  onDecide,
}: {
  approval: ApprovalView;
  now: number;
  waiting: boolean;
  onDecide: (decision: "approve" | "reject") => void;
}) {
  const [view, setView] = useState<"json" | "fields">("json");
  const fields = parsedFields(approval);
  return (
    <Card data-approval={approval.id} className="min-w-0 space-y-5 p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <h2 className="font-serif text-[22px] leading-tight font-normal tracking-tight break-words">
          {approval.tool_id}, version {approval.tool_version}
        </h2>
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

      <dl className="grid overflow-hidden rounded-lg border text-[13px] sm:grid-cols-2">
        <Fact data-approval-requester="true" label="Requested by">
          {requesterText(approval)}
        </Fact>
        <Fact data-approval-reason="true" label="Why it's asking">
          {approval.policy_reason ??
            "not recorded, as this request is older than that record."}
        </Fact>
        <Fact data-approval-run="true" label="Run">
          {approval.run_goal ?? "not recorded."}
        </Fact>
        <Fact data-approval-task="true" label="For task">
          {approval.task_title ?? "not recorded for this call."}
        </Fact>
        <Fact data-approval-scope="true" label="Scope when asked">
          {scopeText(approval)}
        </Fact>
        <Fact data-approval-policy="true" label="Policy version">
          {policyText(approval)}
        </Fact>
        <Fact label="Expires" colon={false}>
          <span className={waiting ? "text-attention" : undefined}>
            {new Date(approval.expires_at).toLocaleString()}.
          </span>{" "}
          <span className="text-muted-foreground">
            ({relative(approval.expires_at, now)})
          </span>
        </Fact>
        {waiting ? (
          <Fact label="Status">Waiting for a decision.</Fact>
        ) : (
          <Fact data-approval-decided="true" label="Decided">
            {decidedText(approval)}
          </Fact>
        )}
      </dl>

      <div className="overflow-hidden rounded-xl border">
        <div className="flex flex-wrap items-center gap-2 border-b px-3.5 py-2 text-[12.5px] dark:bg-muted/40">
          <span className="font-semibold">Exact request</span>
          <span
            data-approval-digest="true"
            className="text-muted-foreground font-mono"
          >
            sha256 {approval.argument_hash.slice(0, 8)}…
            {approval.argument_hash.slice(-4)} ·{" "}
            {approval.arguments_bytes.toLocaleString()} bytes
          </span>
          <span className="flex-1" />
          <div role="group" aria-label="Request view" className="flex gap-1">
            {(
              [
                ["fields", "Fields"],
                ["json", "JSON"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                aria-pressed={view === id}
                disabled={id === "fields" && fields === null}
                onClick={() => setView(id)}
                className={cn(
                  "rounded-md border border-transparent px-2 py-0.5 disabled:opacity-60",
                  view === id && "border-border bg-background dark:bg-accent",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
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
        {view === "fields" && fields !== null ? (
          <dl data-approval-fields="true" className="border-t text-[13.5px]">
            {fields.map(([key, value]) => (
              <div
                key={key}
                className="grid gap-1 border-b px-3.5 py-2.5 last:border-b-0 sm:grid-cols-[8rem_minmax(0,1fr)]"
              >
                <dt className="text-muted-foreground font-mono text-[12.5px]">
                  {key}
                </dt>
                <dd className="min-w-0 space-y-2">
                  {typeof value === "string" ? (
                    <>
                      <pre className="font-mono text-[13px] break-words whitespace-pre-wrap">
                        {value}
                      </pre>
                      {/\n|`|\*\*|^\s*[-*] /m.test(value) ? (
                        <div
                          data-approval-rendered="true"
                          className="rounded-md border px-3 py-2 font-serif text-[15px] leading-relaxed"
                        >
                          <span className="sr-only">Rendered: </span>
                          <Markdown text={value} />
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <pre className="font-mono text-[13px] break-words whitespace-pre-wrap">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <pre
            tabIndex={0}
            className="max-h-96 overflow-auto border-t p-3.5 font-mono text-[13px] leading-relaxed break-words whitespace-pre-wrap dark:bg-muted/30"
          >
            {approval.arguments}
          </pre>
        )}
      </div>
      {approval.arguments_truncated ? (
        <p
          role="alert"
          className="border-destructive/35 text-destructive rounded-lg border p-3 text-sm font-medium"
        >
          {MESSAGES.approval_too_large}
        </p>
      ) : null}

      {waiting ? (
        <>
          <p className={cn(INNER_BOX, "flex items-start gap-3 text-[13.5px]")}>
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
          <div className="flex flex-wrap items-center gap-2.5">
            <Button size="lg" onClick={() => onDecide("approve")}>
              <Check aria-hidden="true" />
              Approve
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => onDecide("reject")}
            >
              Reject
            </Button>
            <span className="text-muted-foreground ml-auto text-[12.5px]">
              Approve ⌘↵ · Reject ⌘⌫, each pressed twice · J and K move
            </span>
          </div>
        </>
      ) : null}
    </Card>
  );
}

// Fields keep the stored order. JSON reorders integer-like keys, so such a request has no Fields view.
function parsedFields(approval: ApprovalView): [string, unknown][] | null {
  if (approval.arguments_truncated) return null;
  try {
    const value: unknown = JSON.parse(approval.arguments);
    if (value === null || typeof value !== "object" || Array.isArray(value))
      return null;
    const entries = Object.entries(value as Record<string, unknown>);
    return entries.some(([key]) => /^\d+$/.test(key)) ? null : entries;
  } catch {
    return null;
  }
}

// A small markdown reader that only builds React text nodes, so nothing is injected as HTML.
function Markdown({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n{2,}/).map((block, index) => {
        const lines = block.split("\n");
        if (lines.every((line) => /^\s*[-*] /.test(line))) {
          return (
            <ul key={index} className="list-disc space-y-1 pl-5">
              {lines.map((line, item) => (
                <li key={item}>{inline(line.replace(/^\s*[-*] /, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={index} className="mb-2 last:mb-0">
            {lines.map((line, item) => (
              <span key={item}>
                {item > 0 ? <br /> : null}
                {inline(line)}
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}

function inline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/).map((part, index) => {
    if (part.length > 1 && part.startsWith("`") && part.endsWith("`"))
      return (
        <code key={index} className="font-mono text-[13px]">
          {part.slice(1, -1)}
        </code>
      );
    if (part.length > 3 && part.startsWith("**") && part.endsWith("**"))
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    return part;
  });
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
