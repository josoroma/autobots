import { Plus } from "lucide-react";

import { HeldNote } from "@/components/held-note";
import type { CreateByName as Create } from "@/components/list-detail/use-create-by-name";
import { Button } from "@/components/ui/button";
import { IconTile } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";

/**
 * A list's create section: a name and Create, then the screen's message, which the suites read as
 * `data-message="create"` (WBLD-09). Create waits for a name and for a pending write.
 */
export function CreateByName({
  heading,
  inputId,
  create,
  message,
}: {
  heading: string;
  inputId: string;
  create: Create;
  message: string | null;
}) {
  return (
    <section
      aria-labelledby="create-heading"
      className="space-y-3 rounded-xl border border-dashed p-5"
    >
      <div className="flex items-center gap-3">
        <IconTile icon={Plus} className="rounded-full" />
        <h2 id="create-heading" className="text-lead font-semibold">
          {heading}
        </h2>
      </div>
      <form
        onSubmit={(event) => void create.create(event)}
        className="flex flex-col gap-3 sm:flex-row sm:items-end"
      >
        <div className="min-w-0 flex-1 space-y-1.5 sm:max-w-sm">
          <Label htmlFor={inputId}>Name</Label>
          <Input
            id={inputId}
            value={create.name}
            onChange={(event) => create.setName(event.target.value)}
            maxLength={100}
            readOnly={create.held}
          />
          {create.held ? <HeldNote /> : null}
        </div>
        <Button
          type="submit"
          disabled={create.name.trim() === "" || create.pending}
        >
          <Plus aria-hidden="true" />
          Create
        </Button>
      </form>
      {message === null ? null : (
        <p role="alert" data-message="create" className="text-sm">
          {message}
        </p>
      )}
    </section>
  );
}
