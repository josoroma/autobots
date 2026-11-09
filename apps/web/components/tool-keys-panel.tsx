"use client";

import {
  parseToolKeyList,
  type ToolKeyList,
  type ToolKeyStatus,
} from "@autobots/api-client";
import { KeyRound } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";

// Decision 0024 and PRD-Tool-Catalog PK-04 to PK-06. A key saved here wins over the environment,
// for this workspace only. The page shows where each key comes from, never the key.
const NAMES: Record<ToolKeyStatus["provider"], string> = {
  tavily: "Tavily",
  jina: "Jina",
};
const TOOLS: Record<ToolKeyStatus["provider"], string> = {
  tavily: "Tavily Search, Tavily Extract, Tavily Map and Tavily Crawl",
  jina: "Search The Web and Extract Website Content",
};

function sourceLabel(key: ToolKeyStatus): string {
  if (key.source === "settings") {
    return "Saved here for this workspace, encrypted on this Mac";
  }
  if (key.source === "environment") {
    return `${key.variable} from the server environment or .env`;
  }
  return "None. Its tools are unavailable";
}

function ToolKeyCard({
  entry,
  busy,
  onSave,
  onRemove,
}: {
  entry: ToolKeyStatus;
  busy: boolean;
  onSave: (provider: ToolKeyStatus["provider"], draft: string) => void;
  onRemove: (provider: ToolKeyStatus["provider"]) => void;
}) {
  const field = `${entry.provider}-key`;
  const saved = entry.source === "settings";
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const draft = String(new FormData(form).get(field));
    // Cleared before the request, so the key never waits in the form, in any outcome.
    form.reset();
    onSave(entry.provider, draft);
  }
  return (
    <Card
      aria-labelledby={`${field}-heading`}
      data-provider={entry.provider}
      className="space-y-4"
    >
      <div className="space-y-1">
        <h2 id={`${field}-heading`} className="text-sm font-semibold">
          {NAMES[entry.provider]}
        </h2>
        <p className="text-muted-foreground text-[12.5px]">
          {TOOLS[entry.provider]}
        </p>
      </div>
      <dl className="grid gap-1 text-[13px] sm:grid-cols-[8rem_minmax(0,1fr)]">
        <dt className="text-muted-foreground">Source</dt>
        <dd data-field="source">{sourceLabel(entry)}</dd>
      </dl>
      <form onSubmit={submit} className="max-w-xl space-y-2">
        <label htmlFor={field} className="block text-sm font-medium">
          {saved ? "Replace key" : "API key"}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            id={field}
            name={field}
            type="password"
            required
            autoComplete="off"
            data-1p-ignore
            spellCheck={false}
            className="sm:flex-1"
          />
          <Button type="submit" disabled={busy} className="shrink-0">
            <KeyRound aria-hidden="true" />
            {busy ? "Saving" : "Save"}
          </Button>
        </div>
      </form>
      {saved ? (
        <div className="space-y-2">
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => onRemove(entry.provider)}
          >
            Remove
          </Button>
          <p className="text-muted-foreground max-w-2xl text-[12.5px] leading-relaxed">
            Remove deletes this workspace&apos;s saved key, so {entry.variable}{" "}
            from the environment or .env applies again. It never edits .env.
          </p>
        </div>
      ) : null}
    </Card>
  );
}

export function ToolKeysPanel() {
  const [keys, setKeys] = useState<ToolKeyList | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const load = useCallback(async () => {
    const reply = await fetch("/api/settings/tool-keys", {
      cache: "no-store",
    }).catch(() => null);
    if (reply?.ok === true) {
      setKeys(parseToolKeyList(await reply.json()));
      setLoadFailed(false);
    } else {
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/settings/tool-keys", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) {
          setKeys(parseToolKeyList(await reply.json()));
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
    provider: ToolKeyStatus["provider"],
    method: "PUT" | "DELETE",
    body: Record<string, unknown>,
  ): Promise<void> {
    setBusy(true);
    setMessage(null);
    const reply = await csrfFetch(`/api/settings/tool-keys/${provider}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => null);
    setBusy(false);
    if (reply?.ok === true) {
      setKeys(parseToolKeyList(await reply.json()));
      setMessage(method === "PUT" ? "Saved." : "Removed.");
    } else {
      const failure = (await reply?.json().catch(() => null)) as {
        message?: string;
      } | null;
      setMessage(failure?.message ?? "That did not work. Nothing changed.");
      await load();
    }
  }

  function version(provider: ToolKeyStatus["provider"]): number {
    return (
      keys?.keys.find((entry) => entry.provider === provider)?.version ?? 0
    );
  }

  if (loadFailed) {
    return (
      <Card>
        <p role="alert" className="text-sm">
          Tool key settings are unavailable. Sign in, and check that the local
          API is running.
        </p>
      </Card>
    );
  }
  if (keys === null) {
    return <p className="text-muted-foreground text-sm">Loading settings.</p>;
  }
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground max-w-2xl text-[13px] leading-relaxed">
        A key saved here is used for this workspace instead of the server
        environment and .env, from the next tool call, with no restart. Saving
        checks the key&apos;s format only and calls no provider. Only the
        workspace owner can save or remove a key.
      </p>
      {message === null ? null : (
        <p role="status" aria-live="polite" className="text-sm font-medium">
          {message}
        </p>
      )}
      {keys.keys.map((entry) => (
        <ToolKeyCard
          key={entry.provider}
          entry={entry}
          busy={busy}
          onSave={(provider, draft) =>
            void mutate(provider, "PUT", {
              draft_key: draft,
              expected_version: version(provider),
            })
          }
          onRemove={(provider) =>
            void mutate(provider, "DELETE", {
              expected_version: version(provider),
            })
          }
        />
      ))}
    </div>
  );
}
