"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";

import { Paperclip, Play, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RunDisclosure } from "@/components/run-disclosure";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  INNER_BOX,
  IconTile,
} from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/field";
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
};

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
  | "model_not_offered";

export function GoalComposer() {
  const restored = useSyncExternalStore(subscribe, storedDraft, () => "");
  const [edited, setEdited] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [profile, setProfile] = useState("");
  const [files, setFiles] = useState<readonly Attached[]>([]);
  const [refusals, setRefusals] = useState<readonly string[]>([]);
  const draft = edited ?? restored;

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

  async function run(): Promise<void> {
    setOutcome(null);
    // One key per press, so a retried request admits one run and each new press is a new intent.
    const reply = await csrfFetch("/api/v1/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({
        goal_text: draft,
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
    } | null;
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
    <Card aria-labelledby="composer-heading" className="flex flex-col gap-6">
      <CardHeader>
        <IconTile icon={Sparkles} />
        <div className="min-w-0 flex-1 space-y-1">
          <CardTitle id="composer-heading">New goal</CardTitle>
          <CardDescription>
            Describe the work, check what it would use, then press Run.
          </CardDescription>
        </div>
      </CardHeader>
      {/* Document order stays goal, model choice, attachments, Run, so Tab never skips back. On wide
          screens the disclosure and attachments sit beside the goal and Run sits at the bottom of the
          goal's column. */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="flex flex-col gap-2">
          <label htmlFor="goal" className="text-sm font-medium">
            Goal
          </label>
          <Textarea
            id="goal"
            value={draft}
            onChange={(event) => update(event.target.value)}
            rows={6}
            className="min-h-36 flex-1 resize-y"
          />
        </div>
        <div className="flex flex-col gap-6 lg:row-span-2">
          <RunDisclosure chosen={profile} onChoose={setProfile} />
          <div className="flex flex-col gap-2" data-field="attachments">
            <label
              htmlFor="attachments"
              className="flex items-center gap-2 text-sm font-medium"
            >
              <Paperclip aria-hidden="true" className="size-4" />
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
              Up to {MAX_FILES} plain text, markdown, JSON or CSV files, 1 MiB
              each. The run can read them under inputs/.
            </p>
            {files.length === 0 ? null : (
              <ul className="space-y-1 text-sm" aria-label="Attached files">
                {files.map((file) => (
                  <li
                    key={file.path}
                    data-attached={file.path}
                    className="flex items-center gap-2"
                  >
                    <code className="truncate">{file.path}</code>
                    <span className="text-muted-foreground text-xs">
                      {file.media_type}
                    </span>
                    <Button
                      type="button"
                      variant="secondary"
                      className="px-2 py-1"
                      aria-label={`Remove ${file.name}`}
                      onClick={() =>
                        setFiles(
                          files.filter((item) => item.path !== file.path),
                        )
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
        </div>
        <Button
          onClick={() => void run()}
          disabled={draft.trim() === ""}
          className="w-full lg:self-end"
        >
          <Play aria-hidden="true" className="size-4" />
          Run
        </Button>
      </div>
      {outcome === null ? null : (
        <p
          role="alert"
          data-outcome={outcome}
          className={cn(INNER_BOX, "text-sm")}
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
