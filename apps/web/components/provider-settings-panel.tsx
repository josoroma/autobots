"use client";

import {
  parseProviderStatus,
  type ProviderStatus,
  type RouteQualification,
} from "@autobots/api-client";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { csrfFetch } from "@/lib/csrf-fetch";

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

function RouteQualifications({ routes }: { routes: RouteQualification[] }) {
  return (
    <Card
      aria-labelledby="qualification-heading"
      data-field="qualification"
      className="space-y-3"
    >
      <h2 id="qualification-heading" className="text-lg font-medium">
        Live qualification
      </h2>
      <p className="text-muted-foreground text-sm">
        What a live test of each route found. A configured key does not mean a
        route was tested, and an available catalog does not either.
      </p>
      {routes.map((route) => (
        <section
          key={route.profile}
          data-route={route.profile}
          aria-label={route.canonical_id}
          className="space-y-2 text-sm"
        >
          <h3 className="font-medium break-all">{route.canonical_id}</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium">Status</dt>
              <dd data-route-field="status">
                {QUALIFICATION_LABELS[route.status]}
              </dd>
            </div>
            {route.qualified_on === null ? null : (
              <div>
                <dt className="font-medium">Tested on</dt>
                <dd data-route-field="date">{route.qualified_on}</dd>
              </div>
            )}
            {route.configuration === null ? null : (
              <div>
                <dt className="font-medium">Configuration</dt>
                <dd data-route-field="configuration">{route.configuration}</dd>
              </div>
            )}
            {route.limits === null ? null : (
              <div>
                <dt className="font-medium">Limits</dt>
                <dd data-route-field="limits">{route.limits}</dd>
              </div>
            )}
          </dl>
        </section>
      ))}
    </Card>
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

  async function mutate(
    path: string,
    method: string,
    body?: unknown,
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
      setMessage("Saved.");
    } else {
      const failure = (await reply?.json().catch(() => null)) as {
        message?: string;
      } | null;
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
      <Card aria-labelledby="openrouter-heading" className="space-y-3">
        <h2 id="openrouter-heading" className="text-lg font-medium">
          OpenRouter
        </h2>
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="font-medium">Source</dt>
            <dd data-field="source">{SOURCE_LABELS[status.source]}</dd>
          </div>
          <div>
            <dt className="font-medium">Authentication</dt>
            <dd data-field="auth">{AUTH_LABELS[status.auth_status]}</dd>
          </div>
          <div>
            <dt className="font-medium">Catalog</dt>
            <dd data-field="catalog">
              {CATALOG_LABELS[status.catalog_status]}
            </dd>
          </div>
          {status.credential_version === null ? null : (
            <div>
              <dt className="font-medium">Stored version</dt>
              <dd data-field="version">{status.credential_version}</dd>
            </div>
          )}
        </dl>
        {message === null ? null : (
          <p role="status" aria-live="polite" className="text-sm font-medium">
            {message}
          </p>
        )}
        {status.source === "environment" ? (
          <p className="text-muted-foreground text-sm">
            This key is set in the server environment. Changing it there needs a
            coordinated restart, and Disconnect does not apply.
          </p>
        ) : (
          <form onSubmit={(event) => void saveKey(event)} className="space-y-2">
            <label htmlFor="openrouter-key" className="text-sm font-medium">
              {hasAppKey ? "Replace key" : "API key"}
            </label>
            <input
              id="openrouter-key"
              name="openrouter-key"
              type="password"
              required
              autoComplete="off"
              data-1p-ignore
              spellCheck={false}
              className="bg-background border-input block w-full rounded-md border px-3 py-2 text-sm"
            />
            <p className="text-muted-foreground text-sm">
              The key is sent to this Mac&apos;s server, checked against
              OpenRouter&apos;s key metadata, then encrypted. It starts no model
              call.
            </p>
            <Button type="submit" disabled={busy}>
              {busy ? "Validating" : "Save & validate"}
            </Button>
          </form>
        )}
        <div className="flex flex-wrap gap-2">
          {status.source === "none" ? null : (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                void mutate(
                  "/api/settings/model-providers/openrouter/validate",
                  "POST",
                )
              }
            >
              Validate
            </Button>
          )}
          {hasAppKey ? (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                void mutate(
                  "/api/settings/model-providers/openrouter/credential",
                  "DELETE",
                  {
                    expected_version: status.settings_version,
                  },
                )
              }
            >
              Disconnect
            </Button>
          ) : null}
        </div>
        {hasAppKey ? (
          <p className="text-muted-foreground text-sm">
            Disconnect removes this workspace&apos;s stored key. It does not
            touch an environment key. A request already sent may still finish.
          </p>
        ) : null}
      </Card>
      <RouteQualifications routes={status.qualification} />
      <Link href="/" className="text-sm font-medium underline">
        Return to your draft
      </Link>
    </>
  );
}
