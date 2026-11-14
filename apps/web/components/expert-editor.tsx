"use client";

import {
  parseExpertView,
  parseToolCatalog,
  type ExpertView,
  type ToolCatalog,
  type ToolDescriptor,
} from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, INNER_BOX } from "@/components/ui/card";
import { Choice, Input, Select, Textarea } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/page-header";
import { AVAILABILITY, repair } from "@/components/tool-catalog";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";

const PROFILES = [
  { id: "", label: "Workspace setting" },
  { id: "openrouter_terra", label: "Terra" },
  { id: "openrouter_sol", label: "Sol" },
];

type Draft = {
  purpose: string;
  instructions: string;
  tools: readonly string[];
  groups: readonly string[];
  executor: string;
};

// What an Expert may be granted, from the same catalog the Tools page shows (TC-06, TS-04).
function grantable(catalog: ToolCatalog | null): ToolDescriptor[] {
  return (catalog?.tools ?? []).filter((tool) =>
    tool.grantable_to.includes("expert"),
  );
}

function members(catalog: ToolCatalog | null, group: string): string[] {
  return grantable(catalog)
    .filter((tool) => tool.group === group)
    .map((tool) => tool.tool_id);
}

// The explicit list a save will record: the tools named, then each whole group's tools.
function expansion(catalog: ToolCatalog | null, draft: Draft): string[] {
  const tools = [...draft.tools];
  for (const group of draft.groups) {
    for (const tool of members(catalog, group)) {
      if (!tools.includes(tool)) tools.push(tool);
    }
  }
  return tools;
}

function draftOf(expert: ExpertView): Draft {
  const latest = expert.versions.at(-1)?.config;
  return {
    purpose: latest?.purpose ?? "",
    instructions: latest?.instructions ?? "",
    tools: latest?.tools ?? [],
    groups: latest?.tool_groups ?? [],
    executor: latest?.role_bindings?.executor ?? "",
  };
}

export function ExpertEditor({ expertId }: { expertId: string }) {
  const router = useRouter();
  const [expert, setExpert] = useState<ExpertView | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [state, setState] = useState<"ready" | "unavailable">("ready");
  const [message, setMessage] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ToolCatalog | null>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/tools", { cache: "no-store" })
      .then(async (reply) => {
        if (active && reply.ok)
          setCatalog(parseToolCatalog(await reply.json()));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

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
  const saved: Record<string, string> =
    expert?.versions.at(-1)?.config.role_bindings ?? {};
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
            tool_groups: draft.groups,
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
            : failure?.code === "expert_tool_unavailable"
              ? "A granted tool is unavailable in this install. Remove it, or configure it first."
              : failure?.code === "expert_tool_group_empty"
                ? "A granted group has no tools an Expert may use."
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
      <p role="status" className="text-muted-foreground text-sm">
        Loading this Expert.
      </p>
    );
  }
  const granted = expansion(catalog, draft);
  return (
    <div className="grid items-start gap-6 @4xl:grid-cols-[minmax(0,1fr)_300px]">
      <Card aria-labelledby="config-heading" className="space-y-6 p-6">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="bg-background grid size-10 shrink-0 place-items-center rounded-[10px] border font-serif text-lg dark:border-transparent dark:bg-muted"
          >
            {expert.name.trim().charAt(0).toUpperCase()}
          </span>
          <h2
            id="config-heading"
            className="font-serif text-[22px] leading-tight font-normal tracking-tight"
          >
            {expert.name}, version {expert.latest_version}
          </h2>
        </div>
        <form onSubmit={(event) => void save(event)} className="space-y-6">
          <div className="space-y-4">
            <div className="space-y-1.5">
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
            <div className="space-y-1.5">
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
          </div>
          <fieldset
            className="space-y-2 border-t pt-5"
            data-field="tool-groups"
          >
            <legend className={LEGEND}>Grant whole groups</legend>
            {catalog === null ? (
              <p className="text-muted-foreground text-sm">
                Loading the tool catalog.
              </p>
            ) : (
              <div className="grid gap-x-6 gap-y-2 @xl:grid-cols-2">
                {catalog.groups
                  .filter((group) => members(catalog, group.group).length > 0)
                  .map((group) => {
                    const tools = grantable(catalog).filter(
                      (tool) => tool.group === group.group,
                    );
                    const blocked = tools.some(
                      (tool) => tool.availability !== "available",
                    );
                    const checked = draft.groups.includes(group.group);
                    return (
                      <label
                        key={group.group}
                        htmlFor={`grant-group-${group.group}`}
                        className="flex items-start gap-2.5 text-sm"
                      >
                        <Choice
                          id={`grant-group-${group.group}`}
                          type="checkbox"
                          checked={checked}
                          disabled={blocked && !checked}
                          className="mt-0.5 shrink-0"
                          onChange={(event) =>
                            setDraft({
                              ...draft,
                              groups: event.target.checked
                                ? [...draft.groups, group.group]
                                : draft.groups.filter(
                                    (item) => item !== group.group,
                                  ),
                            })
                          }
                        />
                        <span>
                          {group.title} group ({tools.length}{" "}
                          {tools.length === 1 ? "tool" : "tools"})
                          {blocked ? ", includes an unavailable tool" : ""}
                        </span>
                      </label>
                    );
                  })}
              </div>
            )}
          </fieldset>
          <fieldset className="space-y-2 border-t pt-5">
            <legend className={LEGEND}>Allowed tools</legend>
            <div className="grid gap-x-6 gap-y-2 @xl:grid-cols-2">
              {grantable(catalog).map((tool) => {
                const named = draft.tools.includes(tool.tool_id);
                const fromGroup = draft.groups.includes(tool.group);
                const unavailable = tool.availability !== "available";
                const fix = repair(tool);
                return (
                  <div key={tool.tool_id} data-tool={tool.tool_id}>
                    <label
                      htmlFor={`grant-tool-${tool.tool_id}`}
                      className="flex items-start gap-2.5 text-sm"
                    >
                      <Choice
                        id={`grant-tool-${tool.tool_id}`}
                        aria-describedby={
                          unavailable
                            ? `grant-tool-${tool.tool_id}-why`
                            : undefined
                        }
                        type="checkbox"
                        checked={named || fromGroup}
                        disabled={unavailable && !named && !fromGroup}
                        className="mt-0.5 shrink-0"
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            tools: event.target.checked
                              ? [...draft.tools, tool.tool_id]
                              : draft.tools.filter(
                                  (item) => item !== tool.tool_id,
                                ),
                            // Unchecking one tool of a whole group means the group isn't whole.
                            groups: event.target.checked
                              ? draft.groups
                              : draft.groups.filter(
                                  (item) => item !== tool.group,
                                ),
                          })
                        }
                      />
                      <span>
                        {tool.title}
                        {tool.approval === "always" ? ", after approval" : ""}
                      </span>
                    </label>
                    {unavailable ? (
                      <p
                        id={`grant-tool-${tool.tool_id}-why`}
                        className="text-muted-foreground ml-6.5 text-xs"
                        data-field="unavailable"
                      >
                        {AVAILABILITY[tool.availability] ?? tool.availability}
                        {fix === null ? "" : `. ${fix}`}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </fieldset>
          <p
            className={cn(INNER_BOX, "text-sm wrap-anywhere")}
            data-field="expansion"
            aria-live="polite"
          >
            {granted.length === 0
              ? "This version grants no tools."
              : `This version grants: ${granted.join(", ")}${
                  draft.groups.length === 0
                    ? "."
                    : `, from ${draft.groups.length === 1 ? "the group" : "the groups"} ${draft.groups.join(", ")} and the tools named.`
                }`}
          </p>
          <div className="space-y-1.5 border-t pt-5">
            <label htmlFor="executor" className="text-sm font-medium">
              Model for its work
            </label>
            <Select
              id="executor"
              value={draft.executor}
              className="sm:max-w-xs"
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
            <p
              data-field="dropped-bindings"
              className="rounded-lg border p-3 text-sm"
            >
              The saved version names a model that isn&apos;t offered for new
              runs for {dropped.join(", ")}. Saving removes that.
            </p>
          )}
          <div className="flex flex-wrap gap-2 border-t pt-5">
            <Button type="submit">Save revision</Button>
            <Button
              type="button"
              variant="outline"
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
      <Card aria-labelledby="versions-heading" className="space-y-3">
        <SectionLabel id="versions-heading">Versions</SectionLabel>
        <ol className="text-sm">
          {expert.versions.map((version) => (
            <li
              key={version.version}
              data-version={version.version}
              className="border-t py-2.5 wrap-anywhere first:border-t-0 first:pt-0"
            >
              <span className="font-medium">Version {version.version}</span>:{" "}
              <span className="text-muted-foreground font-mono text-xs">
                {version.config.tools?.join(", ") || "no tools"}
                {(version.config.tool_groups ?? []).length === 0
                  ? ""
                  : ` (groups: ${(version.config.tool_groups ?? []).join(", ")})`}
              </span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}

// A section label inside the form, kept a native legend so the group keeps its name.
const LEGEND = "text-muted-foreground mb-2 text-xs font-semibold tracking-wide";
