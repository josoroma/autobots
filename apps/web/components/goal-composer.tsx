"use client";

import {
  parseExpertList,
  parseModelList,
  parseRunPreview,
  type ExpertList,
  type ModelList,
  type RunPreview,
} from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";

import { FileText, Paperclip, Play, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DEFAULT_BUDGET_MICRO_USD,
  RunDisclosure,
} from "@/components/run-disclosure";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  INNER_BOX,
} from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/field";
import { focusGoal, NEW_RUN_PARAM } from "@/components/new-run";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";

// The draft and choice survive setup in this tab only. Opening or restoring them never starts anything:
// the one admission below happens only when Run is pressed. No credential is ever kept here.
const DRAFT_KEY = "autobots.draft";
const subscribe = () => () => undefined;

function storedDraft(): string {
  try {
    return window.sessionStorage.getItem(DRAFT_KEY) ?? "";
  } catch {
    return "";
  }
}

// PRD-Tool-Catalog FI-01: up to five text files of at most 1 MiB, kept as run inputs. Nothing is
// sent until Run is pressed, and the files go with that one request.
const MAX_FILES = 5;
const MAX_FILE_BYTES = 1_048_576;
const MEDIA_TYPES: Record<string, string> = {
  txt: "text/plain",
  text: "text/plain",
  md: "text/markdown",
  markdown: "text/markdown",
  json: "application/json",
  csv: "text/csv",
};

type Attached = {
  name: string;
  path: string;
  media_type: string;
  content: string;
  size: number;
};

// HM-02: a file chip shows its size in bytes, KB or MB.
function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function dollars(micro: number): string {
  return `US$${(micro / 1_000_000).toFixed(2)}`;
}

// Chips read as one row of compact, labelled native selects (Decision 0021: no box shadows).
// A chip wraps its label above the select when narrow, and the select shrinks to the row, so nothing
// scrolls sideways at 400% zoom. The select keeps its own right padding for the chevron.
const CHIP =
  "flex min-w-0 max-w-full flex-wrap items-center gap-x-1.5 gap-y-1 text-[13px]";
const CHIP_CONTROL = "min-w-0 max-w-full";
const CHIP_SELECT =
  "h-8 w-auto max-w-full truncate rounded-full py-0 pl-3 text-[13px] leading-8";
const NO_EXPERT = "";

function inputPath(name: string, taken: readonly Attached[]): string {
  const base =
    name.replace(/[^A-Za-z0-9._-]/g, "-").replace(/^[.-]+/, "") || "file";
  let candidate = `inputs/${base.slice(0, 180)}`;
  for (
    let count = 2;
    taken.some((file) => file.path === candidate);
    count += 1
  ) {
    candidate = `inputs/${count}-${base.slice(0, 176)}`;
  }
  return candidate;
}

type Outcome =
  | "queued"
  | "credentials_required"
  | "credential_invalid"
  | "credential_unavailable"
  | "model_refused"
  | "error"
  | "model_not_offered"
  | "budget_refused"
  | "session_failed";

export function GoalComposer() {
  const restored = useSyncExternalStore(subscribe, storedDraft, () => "");
  // Arrived from New run or ⇧⌘O (SH-02): focus the goal, then drop the marker from the address.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get(NEW_RUN_PARAM) !== "1") return;
    focusGoal();
    params.delete(NEW_RUN_PARAM);
    const rest = params.toString();
    window.history.replaceState(
      window.history.state,
      "",
      `${window.location.pathname}${rest === "" ? "" : `?${rest}`}`,
    );
  }, []);
  const [edited, setEdited] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [profile, setProfile] = useState("");
  const [files, setFiles] = useState<readonly Attached[]>([]);
  const [refusals, setRefusals] = useState<readonly string[]>([]);
  const [expertId, setExpertId] = useState(NO_EXPERT);
  const [chosenBudget, setChosenBudget] = useState<number | null>(null);
  const [experts, setExperts] = useState<ExpertList | null>(null);
  const [models, setModels] = useState<ModelList | null>(null);
  const [preview, setPreview] = useState<RunPreview | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const draft = edited ?? restored;

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch("/api/v1/experts", { cache: "no-store" }),
      fetch("/api/models", { cache: "no-store" }),
    ])
      .then(async ([expertReply, modelReply]) => {
        if (!active) return;
        if (expertReply.ok) {
          setExperts(parseExpertList(await expertReply.json()));
        } else {
          await expertReply.text();
        }
        if (modelReply.ok) {
          setModels(parseModelList(await modelReply.json()));
        } else {
          await modelReply.text();
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  // HM-03: what the run would use, from the server, for the current choices. Reading it starts nothing.
  useEffect(() => {
    let active = true;
    const query = new URLSearchParams();
    if (profile !== "") query.set("run_profile", profile);
    if (expertId !== NO_EXPERT) query.set("expert_id", expertId);
    const suffix = query.toString();
    fetch(`/api/v1/run-preview${suffix === "" ? "" : `?${suffix}`}`, {
      cache: "no-store",
    })
      .then(async (reply) => {
        if (!active) return;
        if (!reply.ok) {
          await reply.text();
          setPreviewFailed(true);
          return;
        }
        setPreview(parseRunPreview(await reply.json()));
        setPreviewFailed(false);
      })
      .catch(() => {
        if (active) setPreviewFailed(true);
      });
    return () => {
      active = false;
    };
  }, [profile, expertId]);

  const range = preview?.budget ?? null;
  const budgetSteps: number[] = [];
  if (range !== null) {
    for (
      let value = range.min_micro_usd;
      value <= range.max_micro_usd;
      value += range.step_micro_usd
    ) {
      budgetSteps.push(value);
    }
  }
  const budgetLeft = range === null || budgetSteps.length > 0;
  // The default until a choice is made, and never a value the server no longer offers.
  const budget =
    chosenBudget !== null && budgetSteps.includes(chosenBudget)
      ? chosenBudget
      : (range?.default_micro_usd ?? DEFAULT_BUDGET_MICRO_USD);
  const expert = experts?.experts.find((item) => item.id === expertId) ?? null;
  const expertBindings = expert?.versions.find(
    (version) => version.version === expert.latest_version,
  )?.config.role_bindings;

  async function attach(chosen: FileList | null): Promise<void> {
    const kept = [...files];
    const refused: string[] = [];
    for (const file of Array.from(chosen ?? [])) {
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      const mediaType = MEDIA_TYPES[extension];
      if (kept.length >= MAX_FILES) {
        refused.push(`${file.name}: only ${MAX_FILES} files can be attached.`);
      } else if (mediaType === undefined) {
        refused.push(
          `${file.name}: only plain text, markdown, JSON or CSV can be attached.`,
        );
      } else if (file.size > MAX_FILE_BYTES) {
        refused.push(`${file.name}: a file can be at most 1 MiB.`);
      } else {
        const content = await file.text();
        kept.push({
          name: file.name,
          path: inputPath(file.name, kept),
          media_type: mediaType,
          content,
          size: file.size,
        });
      }
    }
    setFiles(kept);
    setRefusals(refused);
  }

  function update(value: string): void {
    setEdited(value);
    try {
      window.sessionStorage.setItem(DRAFT_KEY, value);
    } catch {
      // Storage is unavailable, so the draft lasts only as long as this page.
    }
  }

  // HM-02: with an Expert, a direct session starts first and the run belongs to it.
  async function startSession(): Promise<string | null> {
    const reply = await csrfFetch("/api/v1/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({
        kind: "direct",
        experts: [{ expert_id: expertId }],
      }),
    }).catch(() => null);
    if (reply?.ok !== true) {
      await reply?.text().catch(() => null);
      return null;
    }
    return ((await reply.json()) as { id: string }).id;
  }

  async function run(): Promise<void> {
    setOutcome(null);
    setRefusal(null);
    let sessionId: string | null = null;
    if (expertId !== NO_EXPERT) {
      sessionId = await startSession();
      if (sessionId === null) {
        setOutcome("session_failed");
        return;
      }
    }
    // One key per press, so a retried request admits one run and each new press is a new intent.
    const reply = await csrfFetch("/api/v1/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({
        goal_text: draft,
        budget_micro_usd: budget,
        ...(sessionId === null ? {} : { session_id: sessionId }),
        ...(profile === "" ? {} : { run_profile: profile }),
        ...(files.length === 0
          ? {}
          : {
              input_documents: files.map(({ path, content, media_type }) => ({
                path,
                content,
                media_type,
              })),
            }),
      }),
    }).catch(() => null);
    if (reply?.ok === true) {
      const accepted = (await reply.json()) as { run_id: string };
      setRunId(accepted.run_id);
      setOutcome("queued");
      setFiles([]);
      setRefusals([]);
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
      message?: string;
    } | null;
    if (failure?.code?.startsWith("budget_") === true) {
      setRefusal(failure.message ?? "That budget can't be used.");
      setOutcome("budget_refused");
      return;
    }
    if (failure?.code === "model_not_offered") {
      setOutcome("model_not_offered");
      return;
    }
    if (reply?.status === 422) {
      setOutcome("model_refused");
      return;
    }
    const known: Outcome[] = [
      "credentials_required",
      "credential_invalid",
      "credential_unavailable",
    ];
    setOutcome(known.find((code) => code === failure?.code) ?? "error");
  }

  return (
    <Card
      aria-labelledby="composer-heading"
      className="border-input flex flex-col rounded-2xl p-0 shadow-lg dark:shadow-black/60"
    >
      <CardHeader className="px-5 pt-5">
        <div className="min-w-0 flex-1 space-y-0.5">
          <CardTitle id="composer-heading" className="font-medium">
            New goal
          </CardTitle>
          <CardDescription>
            Describe the work, check what it would use, then press Run.
          </CardDescription>
        </div>
      </CardHeader>
      {/* Document order stays goal, chips (model, Expert, budget), what the run would use, attachments,
          Run, and the card reads top to bottom in that order, so Tab never climbs. */}
      <div className="flex flex-col gap-1 px-5 pt-4 pb-4">
        <label
          htmlFor="goal"
          className="text-muted-foreground text-xs font-medium"
        >
          Goal
        </label>
        <Textarea
          id="goal"
          value={draft}
          onChange={(event) => update(event.target.value)}
          rows={4}
          className="min-h-28 resize-y rounded-none border-transparent bg-transparent px-0 text-base leading-relaxed dark:bg-transparent"
        />
      </div>
      <div
        role="group"
        aria-label="Run options"
        data-field="composer-chips"
        className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t px-5 py-3"
      >
        <div className={CHIP} data-chip="models">
          <label htmlFor="run-model" className="text-muted-foreground">
            Model for this run
          </label>
          <div className={CHIP_CONTROL}>
            <Select
              id="run-model"
              value={profile}
              onChange={(event) => setProfile(event.target.value)}
              className={CHIP_SELECT}
            >
              <option value="">The workspace setting</option>
              {(models?.models ?? [])
                .filter((model) => model.offered)
                .map((model) => (
                  <option key={model.profile} value={model.profile}>
                    {model.canonical_id}
                  </option>
                ))}
            </Select>
          </div>
        </div>
        <div className={CHIP} data-chip="expert">
          <label htmlFor="run-expert" className="text-muted-foreground">
            Expert
          </label>
          <div className={CHIP_CONTROL}>
            <Select
              id="run-expert"
              value={expertId}
              onChange={(event) => setExpertId(event.target.value)}
              className={CHIP_SELECT}
            >
              <option value={NO_EXPERT}>No Expert, a goal run</option>
              {(experts?.experts ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className={CHIP} data-chip="budget">
          <label htmlFor="run-budget" className="text-muted-foreground">
            Budget
          </label>
          <div className={CHIP_CONTROL}>
            <Select
              id="run-budget"
              value={budgetLeft ? String(budget) : ""}
              disabled={!budgetLeft}
              onChange={(event) => setChosenBudget(Number(event.target.value))}
              className={cn(CHIP_SELECT, "tabular-nums")}
            >
              {range === null ? (
                <option value={String(budget)}>{dollars(budget)}</option>
              ) : budgetLeft ? (
                budgetSteps.map((value) => (
                  <option key={value} value={String(value)}>
                    {dollars(value)}
                  </option>
                ))
              ) : (
                <option value="">Nothing left today</option>
              )}
            </Select>
          </div>
        </div>
        {range === null ? null : (
          <p
            data-field="daily-left"
            className="text-muted-foreground text-[12.5px] tabular-nums"
          >
            {dollars(Math.max(range.remaining_daily_micro_usd, 0))} left of
            today&apos;s cap
          </p>
        )}
      </div>
      <div className="flex flex-col gap-3 border-t px-5 py-4">
        <RunDisclosure
          chosen={profile}
          roleOverrides={expertBindings}
          budgetMicroUsd={budget}
        />
        <div data-field="preview" className="flex flex-col gap-2 text-[13px]">
          {previewFailed ? (
            <p className="text-muted-foreground">
              What this run would use can&apos;t be read right now.
            </p>
          ) : preview === null ? (
            <p className="text-muted-foreground">Loading what it would use.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground mr-1">Models</span>
                <ul className="flex flex-wrap gap-1.5" aria-label="Models">
                  {preview.profiles.map((item) => (
                    <li
                      key={item.profile}
                      data-preview-profile={item.profile}
                      title={item.roles.join(", ")}
                      className="border-border rounded-full border px-2.5 py-0.5"
                    >
                      {item.label} ·{" "}
                      {item.roles.length === 1
                        ? item.roles[0]
                        : `${item.roles.length} roles`}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground mr-1">Tools</span>
                <ul className="flex flex-wrap gap-1.5" aria-label="Tools">
                  {preview.tools.map((tool) => (
                    <li
                      key={tool}
                      data-preview-tool={tool}
                      className="border-border rounded-full border px-2.5 py-0.5 font-mono text-[12px]"
                    >
                      {tool}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </div>
      <div
        className="flex flex-col gap-2 border-t px-5 pt-4"
        data-field="attachments"
      >
        <label
          htmlFor="attachments"
          className="flex items-center gap-2 text-sm font-medium"
        >
          <Paperclip
            aria-hidden="true"
            className="text-muted-foreground size-4"
          />
          Attach files
        </label>
        <Input
          id="attachments"
          type="file"
          multiple
          accept=".txt,.text,.md,.markdown,.json,.csv,text/plain,text/markdown,application/json,text/csv"
          aria-describedby="attachments-help"
          className="min-w-0 file:mr-3 file:border-0 file:bg-transparent file:font-medium"
          onChange={(event) => {
            void attach(event.target.files);
            event.target.value = "";
          }}
        />
        <p id="attachments-help" className="text-muted-foreground text-xs">
          Up to {MAX_FILES} plain text, markdown, JSON or CSV files, 1 MiB each.
          The run can read them under inputs/.
        </p>
        {files.length === 0 ? null : (
          <ul className="flex flex-wrap gap-2 pt-1" aria-label="Attached files">
            {files.map((file) => (
              <li
                key={file.path}
                data-attached={file.path}
                className="bg-background flex max-w-full min-w-0 items-center gap-2.5 rounded-lg border py-1.5 pr-1.5 pl-2 text-[13px]"
              >
                <span
                  aria-hidden="true"
                  className="text-muted-foreground grid size-7 shrink-0 place-items-center rounded-md border"
                >
                  <FileText className="size-3.5" />
                </span>
                <span className="flex min-w-0 flex-col">
                  <span data-field="file-name" className="truncate font-medium">
                    {file.name}
                  </span>
                  <span className="text-muted-foreground truncate text-[11.5px]">
                    <span data-field="file-type">{file.media_type}</span>
                    {" · "}
                    <span data-field="file-size" className="tabular-nums">
                      {fileSize(file.size)}
                    </span>
                  </span>
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7 shrink-0"
                  aria-label={`Remove ${file.name}`}
                  onClick={() =>
                    setFiles(files.filter((item) => item.path !== file.path))
                  }
                >
                  <X aria-hidden="true" className="size-3.5" />
                </Button>
              </li>
            ))}
          </ul>
        )}
        <div aria-live="polite" data-field="attach-refusals">
          {refusals.map((reason) => (
            <p key={reason} className="text-sm">
              {reason}
            </p>
          ))}
        </div>
      </div>
      <div className="flex justify-end px-5 pt-2 pb-4">
        <Button
          onClick={() => void run()}
          disabled={draft.trim() === "" || !budgetLeft}
          size="lg"
          className="rounded-full px-5"
        >
          <Play aria-hidden="true" className="size-4" />
          Run
        </Button>
      </div>
      {outcome === null ? null : (
        <p
          role="alert"
          data-outcome={outcome}
          className={cn(INNER_BOX, "mx-5 mb-5 text-sm")}
        >
          {outcome === "credentials_required" ? (
            <>
              Model-backed work needs an OpenRouter key. Your draft is kept.{" "}
              <Link href="/settings/models" className="font-medium underline">
                Set up OpenRouter
              </Link>
            </>
          ) : outcome === "credential_invalid" ? (
            <>
              The configured key was rejected. Your draft is kept.{" "}
              <Link href="/settings/models" className="font-medium underline">
                Fix it in settings
              </Link>
            </>
          ) : outcome === "credential_unavailable" ? (
            "Credential storage is unavailable, so model-backed work is blocked. Your draft is kept."
          ) : outcome === "model_not_offered" ? (
            <>
              A saved model choice isn&apos;t offered for new runs until
              it&apos;s qualified, so no run started. Your draft is kept.{" "}
              <Link href="/settings/models" className="font-medium underline">
                Change it in settings
              </Link>
            </>
          ) : outcome === "budget_refused" ? (
            <>{refusal} No run started. Your draft is kept.</>
          ) : outcome === "session_failed" ? (
            "The Expert's session could not be started, so no run started. Your draft is kept."
          ) : outcome === "model_refused" ? (
            "That model or request isn't approved, so no run started. Your draft is kept."
          ) : outcome === "queued" ? (
            <>
              Your goal is queued.{" "}
              {runId === null ? null : (
                <Link href={`/runs/${runId}`} className="font-medium underline">
                  Open this run
                </Link>
              )}
            </>
          ) : (
            "That could not be checked. Sign in, then try again. Your draft is kept."
          )}
        </p>
      )}
    </Card>
  );
}
