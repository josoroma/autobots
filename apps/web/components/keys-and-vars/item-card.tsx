import type { KeyOrVar } from "@autobots/api-client";
import { KeyRound, Save } from "lucide-react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { fieldIds, Input, Label, Select } from "@/components/ui/field";
import {
  FIELD,
  fieldLabel,
  sourceLabel,
  TITLE,
  toggleValue,
  USES,
} from "@/lib/keys-and-vars";

// What the item is for, where its value comes from, and the value itself unless it's a secret.
function ItemSummary({ item, field }: { item: KeyOrVar; field: string }) {
  return (
    <>
      <div className="space-y-1">
        <h2 id={`${field}-heading`} className="text-sm font-semibold">
          {TITLE[item.name]}
        </h2>
        <p
          id={fieldIds(field).description}
          className="text-muted-foreground text-meta"
        >
          {USES[item.name]}
        </p>
      </div>
      <dl className="grid gap-1 text-ui sm:grid-cols-[8rem_minmax(0,1fr)]">
        <dt className="text-muted-foreground">Source</dt>
        <dd data-field="source">{sourceLabel(item)}</dd>
        {item.kind === "secret" ? null : (
          <>
            <dt className="text-muted-foreground">Value</dt>
            <dd data-field="value" className="font-mono text-meta">
              {item.value ?? "None"}
            </dd>
          </>
        )}
      </dl>
    </>
  );
}

function ItemControl({ item, field }: { item: KeyOrVar; field: string }) {
  const control = FIELD[item.name];
  if (control.control === "toggle") {
    return (
      <Select
        id={field}
        name={field}
        aria-describedby={fieldIds(field).description}
        defaultValue={toggleValue(item)}
        className="sm:flex-1"
      >
        <option value="enabled">Enabled</option>
        <option value="disabled">Disabled</option>
      </Select>
    );
  }
  const secret = item.kind === "secret";
  return (
    <Input
      id={field}
      name={field}
      aria-describedby={fieldIds(field).description}
      type={secret ? "password" : "text"}
      required
      autoComplete="off"
      data-1p-ignore
      spellCheck={false}
      placeholder={control.placeholder}
      defaultValue={secret ? undefined : (item.value ?? undefined)}
      className="sm:flex-1"
    />
  );
}

function RemoveSaved({
  item,
  busy,
  onRemove,
}: {
  item: KeyOrVar;
  busy: boolean;
  onRemove: () => void;
}) {
  return (
    <div className="space-y-2">
      <Button variant="outline" disabled={busy} onClick={onRemove}>
        Remove
      </Button>
      <p className="text-muted-foreground max-w-2xl text-meta leading-relaxed">
        Remove deletes this workspace&apos;s saved{" "}
        {item.kind === "secret" ? "key" : "value"}, so {item.variable} from the
        environment or .env applies again. It never edits .env.
      </p>
    </div>
  );
}

/** One key or var: what it's for, where it comes from, its field, and Remove once it's saved here. */
export function ItemCard({
  item,
  busy,
  saving,
  onSave,
  onRemove,
}: {
  item: KeyOrVar;
  /** A write is pending for some item, so none can be sent. */
  busy: boolean;
  /** The pending write is this item's. */
  saving: boolean;
  onSave: (value: string) => void;
  onRemove: () => void;
}) {
  const field = `${item.name}-value`;
  const secret = item.kind === "secret";

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const form = event.currentTarget;
    const value = String(new FormData(form).get(field));
    // A secret is cleared before the request, so it never waits in the form, in any outcome.
    if (secret) form.reset();
    onSave(value);
  }

  return (
    <Card
      aria-labelledby={`${field}-heading`}
      data-item={item.name}
      className="space-y-4"
    >
      <ItemSummary item={item} field={field} />
      <form onSubmit={submit} className="max-w-xl space-y-2">
        <Label htmlFor={field} className="block">
          {fieldLabel(item)}
        </Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <ItemControl item={item} field={field} />
          <Button type="submit" disabled={busy} className="shrink-0">
            {secret ? (
              <KeyRound aria-hidden="true" />
            ) : (
              <Save aria-hidden="true" />
            )}
            {saving ? "Saving" : "Save"}
          </Button>
        </div>
      </form>
      {item.source === "settings" ? (
        <RemoveSaved item={item} busy={busy} onRemove={onRemove} />
      ) : null}
    </Card>
  );
}
