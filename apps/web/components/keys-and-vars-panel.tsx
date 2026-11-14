"use client";

import {
  parseKeysAndVars,
  type KeyOrVar,
  type KeysAndVars,
} from "@autobots/api-client";
import { KeyRound, Save } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";
import { refusalText } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

// Decisions 0024 and 0025, PRD-Tool-Catalog PK-04 to PK-08. A value saved here wins over the
// environment and .env, for this workspace only. A secret is never shown, only where it comes from.
type Name = KeyOrVar["name"];

const TITLES: Record<Name, string> = {
  tavily: "Tavily",
  jina: "Jina",
  github_token: "GitHub token",
  github_repository: "GitHub repository",
  browser_executor: "Browsing",
};
const USES: Record<Name, string> = {
  tavily: "Tavily Search, Tavily Extract, Tavily Map and Tavily Crawl",
  jina: "Search The Web and Extract Website Content",
  github_token:
    "The GitHub tools. A fine-grained token limited to the one repository",
  github_repository: "The one repository the GitHub tools use, as owner/name",
  browser_executor:
    "Browse goal, once the browser executor is qualified. Every call still waits for approval",
};

// R-19 step 4: this screen's words for a refusal's code. Any other keeps the service's own, which
// are fixed per item and never echo what was submitted.
const REFUSALS: Readonly<Record<string, string>> = {
  not_signed_in:
    "Your session ended. Sign in, then try again. Nothing changed.",
  owner_required: "Only the workspace owner can save or remove one.",
};
const LOST =
  "The reply was lost, so this may have applied. What's shown is reloaded.";

function sourceLabel(item: KeyOrVar): string {
  if (item.source === "settings") {
    return item.kind === "secret"
      ? "Saved here for this workspace, encrypted on this Mac"
      : "Saved here for this workspace";
  }
  if (item.source === "environment") {
    return `${item.variable} from the server environment or .env`;
  }
  return item.kind === "secret"
    ? "None. Its tools are unavailable"
    : `None. ${item.variable} isn't set`;
}

function ItemCard({
  item,
  busy,
  onSave,
  onRemove,
}: {
  item: KeyOrVar;
  busy: boolean;
  onSave: (name: Name, value: string) => void;
  onRemove: (name: Name) => void;
}) {
  const field = `${item.name}-value`;
  const saved = item.source === "settings";
  const secret = item.kind === "secret";
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const value = String(new FormData(form).get(field));
    // A secret is cleared before the request, so it never waits in the form, in any outcome.
    if (secret) form.reset();
    onSave(item.name, value);
  }
  return (
    <Card
      aria-labelledby={`${field}-heading`}
      data-item={item.name}
      className="space-y-4"
    >
      <div className="space-y-1">
        <h2 id={`${field}-heading`} className="text-sm font-semibold">
          {TITLES[item.name]}
        </h2>
        <p className="text-muted-foreground text-[12.5px]">{USES[item.name]}</p>
      </div>
      <dl className="grid gap-1 text-[13px] sm:grid-cols-[8rem_minmax(0,1fr)]">
        <dt className="text-muted-foreground">Source</dt>
        <dd data-field="source">{sourceLabel(item)}</dd>
        {secret ? null : (
          <>
            <dt className="text-muted-foreground">Value</dt>
            <dd data-field="value" className="font-mono text-[12.5px]">
              {item.value ?? "None"}
            </dd>
          </>
        )}
      </dl>
      <form onSubmit={submit} className="max-w-xl space-y-2">
        <label htmlFor={field} className="block text-sm font-medium">
          {secret
            ? saved
              ? "Replace key"
              : "API key"
            : "Set for this workspace"}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          {item.name === "browser_executor" ? (
            <Select
              id={field}
              name={field}
              defaultValue={item.value === "enabled" ? "enabled" : "disabled"}
              className="sm:flex-1"
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </Select>
          ) : (
            <Input
              id={field}
              name={field}
              type={secret ? "password" : "text"}
              required
              autoComplete="off"
              data-1p-ignore
              spellCheck={false}
              placeholder={
                item.name === "github_repository" ? "owner/name" : undefined
              }
              defaultValue={secret ? undefined : (item.value ?? undefined)}
              className="sm:flex-1"
            />
          )}
          <Button type="submit" disabled={busy} className="shrink-0">
            {secret ? (
              <KeyRound aria-hidden="true" />
            ) : (
              <Save aria-hidden="true" />
            )}
            {busy ? "Saving" : "Save"}
          </Button>
        </div>
      </form>
      {saved ? (
        <div className="space-y-2">
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => onRemove(item.name)}
          >
            Remove
          </Button>
          <p className="text-muted-foreground max-w-2xl text-[12.5px] leading-relaxed">
            Remove deletes this workspace&apos;s saved{" "}
            {secret ? "key" : "value"}, so {item.variable} from the environment
            or .env applies again. It never edits .env.
          </p>
        </div>
      ) : null}
    </Card>
  );
}

export function KeysAndVarsPanel() {
  const [items, setItems] = useState<KeysAndVars | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  // One write at a time. None sends a key, and each replaces an item whole, so none is held (R-19).
  const writes = useSubmit();
  const busy = writes.pending;

  const load = useCallback(async () => {
    const reply = await fetch("/api/settings/keys-and-vars", {
      cache: "no-store",
    }).catch(() => null);
    if (reply?.ok === true) {
      setItems(parseKeysAndVars(await reply.json()));
      setLoadFailed(false);
    } else {
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/settings/keys-and-vars", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) {
          setItems(parseKeysAndVars(await reply.json()));
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

  function version(name: Name): number {
    return items?.items.find((item) => item.name === name)?.version ?? 0;
  }

  async function mutate(
    name: Name,
    method: "PUT" | "DELETE",
    body: Record<string, unknown>,
  ): Promise<void> {
    setMessage(null);
    const result = await writes.submit({
      body: () => JSON.stringify(body),
      send: ({ body: text }) =>
        csrfFetch(`/api/settings/keys-and-vars/${name}`, {
          method,
          headers: { "Content-Type": "application/json" },
          body: text,
        }),
      parse: parseKeysAndVars,
      keyed: false,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      setItems(result.value);
      setMessage(method === "PUT" ? "Saved." : "Removed.");
      return;
    }
    setMessage(refusalText(REFUSALS, result.refusal, LOST));
    await load();
  }

  if (loadFailed) {
    return (
      <Card>
        <p role="alert" className="text-sm">
          Keys &amp; vars are unavailable. Sign in, and check that the local API
          is running.
        </p>
      </Card>
    );
  }
  if (items === null) {
    return <p className="text-muted-foreground text-sm">Loading settings.</p>;
  }
  const card = (item: KeyOrVar) => (
    <ItemCard
      key={item.name}
      item={item}
      busy={busy}
      onSave={(name, value) =>
        void mutate(name, "PUT", { value, expected_version: version(name) })
      }
      onRemove={(name) =>
        void mutate(name, "DELETE", { expected_version: version(name) })
      }
    />
  );
  return (
    <div className="space-y-6">
      <p className="text-muted-foreground max-w-2xl text-[13px] leading-relaxed">
        A key or value saved here is used for this workspace instead of the
        server environment and .env, from the next tool call, with no restart.
        Saving checks a key&apos;s format only and calls no provider. Only the
        workspace owner can save or remove one.
      </p>
      {message === null ? null : (
        <p role="status" aria-live="polite" className="text-sm font-medium">
          {message}
        </p>
      )}
      <section aria-labelledby="keys-heading" className="space-y-4">
        <h2 id="keys-heading" className="text-sm font-semibold">
          Keys
        </h2>
        {items.items.filter((item) => item.kind === "secret").map(card)}
      </section>
      <section aria-labelledby="vars-heading" className="space-y-4">
        <h2 id="vars-heading" className="text-sm font-semibold">
          Vars
        </h2>
        {items.items.filter((item) => item.kind === "value").map(card)}
      </section>
    </div>
  );
}
