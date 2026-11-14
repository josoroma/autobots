"use client";

import {
  parseProviderStatus,
  type ProviderStatus,
  type RouteQualification,
} from "@autobots/api-client";
import { Cpu, KeyRound } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, IconTile } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";
import { readErrorResponse } from "@/lib/replies";

const AUTH_LABELS: Record<ProviderStatus["auth_status"], string> = {
  missing:
    "No key is configured. Local work is available, and model-backed work is blocked.",
  configured: "The key authenticated.",
  invalid: "The key was rejected. Model-backed work is blocked.",
  unavailable:
    "Authentication or credential storage could not be reached. Model-backed work is blocked.",
};
const CATALOG_LABELS: Record<ProviderStatus["catalog_status"], string> = {
  available: "Available",
  unavailable:
    "Unavailable. New model calls stay blocked until fresh metadata exists.",
  unknown: "Not checked",
};
const SOURCE_LABELS: Record<ProviderStatus["source"], string> = {
  none: "None",
  app: "Stored for this workspace, encrypted on this Mac",
  environment: "The server environment, which is managed outside the app",
};

const QUALIFICATION_LABELS: Record<RouteQualification["status"], string> = {
  qualified_with_limits: "Qualified, with the limits below",
  not_qualified: "Not qualified",
};
const QUALIFICATION_TONES: Record<
  RouteQualification["status"],
  "success" | "muted"
> = {
  qualified_with_limits: "success",
  not_qualified: "muted",
};

// Decorative dots beside each status. The words carry the meaning; the dot only repeats it.
type Tone = "ok" | "bad" | "idle";
const AUTH_TONES: Record<ProviderStatus["auth_status"], Tone> = {
  missing: "idle",
  configured: "ok",
  invalid: "bad",
  unavailable: "bad",
};
const CATALOG_TONES: Record<ProviderStatus["catalog_status"], Tone> = {
  available: "ok",
  unavailable: "bad",
  unknown: "idle",
};
const DOT: Record<Tone, string> = {
  ok: "bg-success-text",
  bad: "bg-destructive",
  idle: "border-muted-foreground border-[1.5px]",
};

function StatusDot({ tone }: { tone: Tone }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "mt-[7px] inline-block size-[7px] shrink-0 rounded-full",
        DOT[tone],
      )}
    />
  );
}

// A labeled cell of the connection bar.
const CELL = "min-w-0 px-[18px] py-3.5";
const CELL_LABEL = "text-muted-foreground mb-[3px] text-xs";

function RouteQualifications({ routes }: { routes: RouteQualification[] }) {
  return (
    <section
      aria-labelledby="qualification-heading"
      data-field="qualification"
      className="space-y-3"
    >
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <h2 id="qualification-heading" className="text-sm font-semibold">
          Live qualification
        </h2>
        <p className="text-muted-foreground text-[12.5px]">
          What a live test of each route found. A configured key does not mean a
          route was tested, and an available catalog does not either.
        </p>
      </div>
      <div className="grid gap-3.5 md:grid-cols-2 xl:grid-cols-3">
        {routes.map((route) => (
          <section
            key={route.profile}
            data-route={route.profile}
            aria-label={route.canonical_id}
            className="bg-card text-card-foreground border-border flex min-w-0 flex-col gap-3 rounded-xl border px-[18px] py-4"
          >
            <h3 className="font-mono text-[12.5px] font-medium break-all">
              {route.canonical_id}
            </h3>
            <dl className="border-border space-y-2 border-t pt-3 text-[13px]">
              <div className="grid grid-cols-[6rem_minmax(0,1fr)] items-start gap-3">
                <dt className="text-muted-foreground">Status</dt>
                <dd data-route-field="status">
                  <Badge
                    variant={QUALIFICATION_TONES[route.status]}
                    className="whitespace-normal"
                  >
                    {QUALIFICATION_LABELS[route.status]}
                  </Badge>
                </dd>
              </div>
              {route.qualified_on === null ? null : (
                <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-3">
                  <dt className="text-muted-foreground">Tested on</dt>
                  <dd data-route-field="date">{route.qualified_on}</dd>
                </div>
              )}
              {route.configuration === null ? null : (
                <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-3">
                  <dt className="text-muted-foreground">Configuration</dt>
                  <dd data-route-field="configuration" className="break-words">
                    {route.configuration}
                  </dd>
                </div>
              )}
              {route.limits === null ? null : (
                <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-3">
                  <dt className="text-muted-foreground">Limits</dt>
                  <dd data-route-field="limits" className="break-words">
                    {route.limits}
                  </dd>
                </div>
              )}
            </dl>
          </section>
        ))}
      </div>
    </section>
  );
}

export function ProviderSettingsPanel() {
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const load = useCallback(async () => {
    const reply = await fetch("/api/settings/model-providers", {
      cache: "no-store",
    }).catch(() => null);
    if (reply?.ok === true) {
      setStatus(parseProviderStatus(await reply.json()));
      setLoadFailed(false);
    } else {
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/settings/model-providers", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) {
          setStatus(parseProviderStatus(await reply.json()));
        } else {
          setLoadFailed(true);
        }
      })
      .catch(() => {
        if (active) setLoadFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  // R-19: each action says what it did, so Validate and Disconnect no longer report "Saved.".
  async function mutate(
    path: string,
    method: string,
    body?: unknown,
    done = "Saved.",
  ): Promise<void> {
    setBusy(true);
    setMessage(null);
    const reply = await csrfFetch(path, {
      method,
      ...(body === undefined
        ? {}
        : {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
    }).catch(() => null);
    setBusy(false);
    if (reply?.ok === true) {
      setStatus(parseProviderStatus(await reply.json()));
      setMessage(done);
    } else {
      const failure = await readErrorResponse(reply);
      setMessage(failure?.message ?? "That did not work. Nothing changed.");
      await load();
    }
  }

  async function saveKey(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (status === null) return;
    const form = event.currentTarget;
    const draft = new FormData(form).get("openrouter-key");
    // Cleared before the request, so the key never waits in the form, in any outcome.
    form.reset();
    await mutate("/api/settings/model-providers/openrouter/credential", "PUT", {
      draft_key: String(draft),
      expected_version: status.settings_version,
    });
  }

  if (loadFailed) {
    return (
      <Card>
        <p role="alert" className="text-sm">
          Provider settings are unavailable. Sign in, and check that the local
          API is running.
        </p>
      </Card>
    );
  }
  if (status === null) {
    return <p className="text-muted-foreground text-sm">Loading settings.</p>;
  }
  const hasAppKey = status.source === "app";
  return (
    <>
      <Card
        aria-labelledby="openrouter-heading"
        className="overflow-hidden p-0"
      >
        <div className="flex flex-col lg:flex-row">
          <div className="flex items-center gap-3 px-[18px] py-3.5 lg:w-48 lg:shrink-0">
            <IconTile icon={Cpu} />
            <h2 id="openrouter-heading" className="text-sm font-semibold">
              OpenRouter
            </h2>
          </div>
          <dl className="divide-border border-border grid min-w-0 flex-1 divide-y border-t text-[13px] lg:auto-cols-fr lg:grid-flow-col lg:divide-x lg:divide-y-0 lg:border-t-0 lg:border-l">
            <div className={CELL}>
              <dt className={CELL_LABEL}>Source</dt>
              <dd data-field="source">{SOURCE_LABELS[status.source]}</dd>
            </div>
            <div className={CELL}>
              <dt className={CELL_LABEL}>Authentication</dt>
              <dd data-field="auth" className="flex gap-2">
                <StatusDot tone={AUTH_TONES[status.auth_status]} />
                {AUTH_LABELS[status.auth_status]}
              </dd>
            </div>
            <div className={CELL}>
              <dt className={CELL_LABEL}>Catalog</dt>
              <dd data-field="catalog" className="flex gap-2">
                <StatusDot tone={CATALOG_TONES[status.catalog_status]} />
                {CATALOG_LABELS[status.catalog_status]}
              </dd>
            </div>
            {status.credential_version === null ? null : (
              <div className={CELL}>
                <dt className={CELL_LABEL}>Stored version</dt>
                <dd data-field="version" className="tabular-nums">
                  {status.credential_version}
                </dd>
              </div>
            )}
          </dl>
        </div>
        <div className="border-border space-y-4 border-t px-[18px] py-4">
          {message === null ? null : (
            <p role="status" aria-live="polite" className="text-sm font-medium">
              {message}
            </p>
          )}
          {status.source === "environment" ? (
            <p className="text-muted-foreground max-w-2xl text-[13px]">
              This key is set in the server environment. Changing it there needs
              a coordinated restart, and Disconnect does not apply.
            </p>
          ) : (
            <form
              onSubmit={(event) => void saveKey(event)}
              className="max-w-xl space-y-2"
            >
              <label
                htmlFor="openrouter-key"
                className="block text-sm font-medium"
              >
                {hasAppKey ? "Replace key" : "API key"}
              </label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="openrouter-key"
                  name="openrouter-key"
                  type="password"
                  required
                  autoComplete="off"
                  data-1p-ignore
                  spellCheck={false}
                  className="sm:flex-1"
                />
                <Button type="submit" disabled={busy} className="shrink-0">
                  <KeyRound aria-hidden="true" />
                  {busy ? "Validating" : "Save & validate"}
                </Button>
              </div>
              <p className="text-muted-foreground text-[12.5px] leading-relaxed">
                The key is sent to this Mac&apos;s server, checked against
                OpenRouter&apos;s key metadata, then encrypted. It starts no
                model call.
              </p>
            </form>
          )}
          {status.source === "none" ? null : (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void mutate(
                    "/api/settings/model-providers/openrouter/validate",
                    "POST",
                    undefined,
                    "Checked. The key's status above is current.",
                  )
                }
              >
                Validate
              </Button>
              {hasAppKey ? (
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() =>
                    void mutate(
                      "/api/settings/model-providers/openrouter/credential",
                      "DELETE",
                      {
                        expected_version: status.settings_version,
                      },
                      "Disconnected. The saved key is removed.",
                    )
                  }
                >
                  Disconnect
                </Button>
              ) : null}
            </div>
          )}
          {hasAppKey ? (
            <p className="text-muted-foreground max-w-2xl text-[12.5px] leading-relaxed">
              Disconnect removes this workspace&apos;s stored key. It does not
              touch an environment key. A request already sent may still finish.
            </p>
          ) : null}
        </div>
      </Card>
      <RouteQualifications routes={status.qualification} />
      <Link href="/" className="inline-block text-sm font-medium underline">
        Return to your draft
      </Link>
    </>
  );
}
