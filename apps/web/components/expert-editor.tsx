"use client";

import { parseExpertView, type ExpertView } from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Choice, Input, Select, Textarea } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";

const TOOLS = [
  { id: "calculate", label: "Calculate" },
  { id: "read_run_file", label: "Read run files" },
  { id: "save_artifact", label: "Save run files" },
  { id: "publish_artifact", label: "Publish artifacts" },
  { id: "search_memory", label: "Search memory" },
  { id: "propose_improvement", label: "Propose improvements for review" },
  { id: "create_github_issue", label: "Create GitHub issues, after approval" },
];
const PROFILES = [
  { id: "", label: "Workspace setting" },
  { id: "openrouter_terra", label: "Terra" },
];

type Draft = {
  purpose: string;
  instructions: string;
  tools: readonly string[];
  executor: string;
};

function draftOf(expert: ExpertView): Draft {
  const latest = expert.versions.at(-1)?.config;
  return {
    purpose: latest?.purpose ?? "",
    instructions: latest?.instructions ?? "",
    tools: latest?.tools ?? [],
    executor: String(latest?.role_bindings?.executor ?? ""),
  };
}

export function ExpertEditor({ expertId }: { expertId: string }) {
  const router = useRouter();
  const [expert, setExpert] = useState<ExpertView | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [state, setState] = useState<"ready" | "unavailable">("ready");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`/api/v1/experts/${encodeURIComponent(expertId)}`, {
      cache: "no-store",
    })
      .then(async (reply) => {
        if (!active) return;
        if (!reply.ok) {
          setState("unavailable");
          return;
        }
        const loaded = parseExpertView(await reply.json());
        setExpert(loaded);
        setDraft(draftOf(loaded));
      })
      .catch(() => {
        if (active) setState("unavailable");
      });
    return () => {
      active = false;
    };
  }, [expertId]);

  // This form edits only the executor. Other offered bindings stay, and one naming a model that
  // isn't offered goes with this save, which the form says, since it would otherwise refuse it.
  const saved = (expert?.versions.at(-1)?.config.role_bindings ?? {}) as Record<
    string,
    string
  >;
  const others = Object.entries(saved).filter(([role]) => role !== "executor");
  const kept = Object.fromEntries(
    others.filter(([, profile]) =>
      PROFILES.some((item) => item.id === profile),
    ),
  );
  const dropped = others
    .filter(([, profile]) => !PROFILES.some((item) => item.id === profile))
    .map(([role]) => role);

  async function save(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (expert === null || draft === null) return;
    setMessage(null);
    const reply = await csrfFetch(
      `/api/v1/experts/${encodeURIComponent(expert.id)}/versions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          expected_version: expert.latest_version,
          config: {
            // What this form doesn't edit, such as skills, stays as it was.
            ...expert.versions.at(-1)?.config,
            purpose: draft.purpose,
            instructions: draft.instructions,
            tools: draft.tools,
            role_bindings: {
              ...kept,
              ...(draft.executor === "" ? {} : { executor: draft.executor }),
            },
          },
        }),
      },
    ).catch(() => null);
    if (reply?.ok === true) {
      const saved = parseExpertView(await reply.json());
      setExpert(saved);
      setDraft(draftOf(saved));
      setMessage(
        `Saved as version ${saved.latest_version}. Work already started keeps its version.`,
      );
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
      message?: string;
    } | null;
    setMessage(
      failure?.code === "model_not_offered"
        ? (failure.message ?? "That model isn't offered for new runs.")
        : failure?.code === "owner_required"
          ? "Only the workspace owner can save a revision."
          : failure?.code === "expert_version_conflict"
            ? "Someone saved a newer version. Reload to see it."
            : "That could not be saved.",
    );
  }

  async function startSession(): Promise<void> {
    if (expert === null) return;
    const reply = await csrfFetch("/api/v1/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({
        kind: "direct",
        experts: [{ expert_id: expert.id }],
      }),
    }).catch(() => null);
    if (reply?.ok === true) {
      const session = (await reply.json()) as { id: string };
      router.push(`/sessions/${session.id}`);
    } else {
      setMessage("That session could not be started.");
    }
  }

  if (state === "unavailable") {
    return (
      <p role="alert" data-state="unavailable" className="text-sm">
        That Expert is not available.
      </p>
    );
  }
  if (expert === null || draft === null) {
    return (
      <p role="status" className="text-sm">
        Loading this Expert.
      </p>
    );
  }
  return (
    <>
      <Card aria-labelledby="config-heading" className="space-y-3">
        <h2 id="config-heading" className="text-lg font-medium">
          {expert.name}, version {expert.latest_version}
        </h2>
        <form onSubmit={(event) => void save(event)} className="space-y-3">
          <div className="space-y-1">
            <label htmlFor="purpose" className="text-sm font-medium">
              Purpose
            </label>
            <Input
              id="purpose"
              value={draft.purpose}
              onChange={(event) =>
                setDraft({ ...draft, purpose: event.target.value })
              }
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="instructions" className="text-sm font-medium">
              Instructions
            </label>
            <Textarea
              id="instructions"
              rows={5}
              value={draft.instructions}
              onChange={(event) =>
                setDraft({ ...draft, instructions: event.target.value })
              }
            />
          </div>
          <fieldset className="space-y-1">
            <legend className="text-sm font-medium">Allowed tools</legend>
            {TOOLS.map((tool) => (
              <label key={tool.id} className="flex items-center gap-2 text-sm">
                <Choice
                  type="checkbox"
                  checked={draft.tools.includes(tool.id)}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      tools: event.target.checked
                        ? [...draft.tools, tool.id]
                        : draft.tools.filter((item) => item !== tool.id),
                    })
                  }
                />
                {tool.label}
              </label>
            ))}
          </fieldset>
          <div className="space-y-1">
            <label htmlFor="executor" className="text-sm font-medium">
              Model for its work
            </label>
            <Select
              id="executor"
              value={draft.executor}
              onChange={(event) =>
                setDraft({ ...draft, executor: event.target.value })
              }
            >
              {PROFILES.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.label}
                </option>
              ))}
              {PROFILES.some(
                (profile) => profile.id === draft.executor,
              ) ? null : (
                <option value={draft.executor} disabled>
                  {draft.executor}: not offered for new runs until qualified
                </option>
              )}
            </Select>
          </div>
          {dropped.length === 0 ? null : (
            <p data-field="dropped-bindings" className="text-sm">
              The saved version names a model that isn&apos;t offered for new
              runs for {dropped.join(", ")}. Saving removes that.
            </p>
          )}
          <div className="flex gap-3">
            <Button type="submit">Save revision</Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void startSession()}
            >
              Start a session
            </Button>
          </div>
        </form>
        {message === null ? null : (
          <p role="status" data-message="save" className="text-sm">
            {message}
          </p>
        )}
      </Card>
      <Card aria-labelledby="versions-heading" className="space-y-2">
        <h2 id="versions-heading" className="text-lg font-medium">
          Versions
        </h2>
        <ol className="space-y-1 text-sm">
          {expert.versions.map((version) => (
            <li key={version.version} data-version={version.version}>
              Version {version.version}:{" "}
              {version.config.tools?.join(", ") || "no tools"}
            </li>
          ))}
        </ol>
      </Card>
    </>
  );
}
