import { KeyRound } from "lucide-react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { fieldIds, Input, Label } from "@/components/ui/field";

const FIELD = "openrouter-key";

/**
 * The OpenRouter key field. Server keys "never reach props, caches, bundles or public events"
 * (nextjs.md), so the field is uncontrolled, the key goes straight into the request, and the form is
 * cleared before the request is sent, so the key never waits in the form, in any outcome.
 */
export function KeyForm({
  replacing,
  pending,
  onSubmit,
}: {
  /** A key is stored for this workspace, so a new one replaces it. */
  replacing: boolean;
  pending: boolean;
  onSubmit: (draft: string) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const form = event.currentTarget;
    const draft = String(new FormData(form).get(FIELD));
    form.reset();
    onSubmit(draft);
  }

  return (
    <form onSubmit={submit} className="max-w-xl space-y-2">
      <Label htmlFor={FIELD} className="block">
        {replacing ? "Replace key" : "API key"}
      </Label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          id={FIELD}
          name={FIELD}
          type="password"
          required
          autoComplete="off"
          data-1p-ignore
          spellCheck={false}
          aria-describedby={fieldIds(FIELD).description}
          className="sm:flex-1"
        />
        <Button type="submit" disabled={pending} className="shrink-0">
          <KeyRound aria-hidden="true" />
          {pending ? "Validating" : "Save & validate"}
        </Button>
      </div>
      <p
        id={fieldIds(FIELD).description}
        className="text-muted-foreground text-meta leading-relaxed"
      >
        The key is sent to this Mac&apos;s server, checked against
        OpenRouter&apos;s key metadata, then encrypted. It starts no model call.
      </p>
    </form>
  );
}

/** Said instead of the field when the key comes from the server environment. */
export function EnvironmentKeyNote() {
  return (
    <p className="text-muted-foreground max-w-2xl text-ui">
      This key is set in the server environment. Changing it there needs a
      coordinated restart, and Disconnect does not apply.
    </p>
  );
}
