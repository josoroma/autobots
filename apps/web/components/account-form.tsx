"use client";

import { updateProfile, type ProfileUpdate } from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/field";
import { writes } from "@/lib/api/browser";
import { refusalText } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

// R-19 step 4: this screen's words for a refusal's code. Any other keeps the service's own.
const REFUSALS: Readonly<Record<string, string>> = {
  display_name_invalid:
    "A display name needs 1 to 60 characters. Nothing changed.",
};
const LOST =
  "The reply was lost, so the name may have saved. Saving again sends it again.";

// PRD-Studio SE-04 and ID-01: edit only your own display name. The API refuses an empty or
// overlong name with display_name_invalid, and the saved name stays as it was.
export function AccountForm({ initial }: { initial: string }) {
  const router = useRouter();
  const [name, setName] = useState(initial);
  const [message, setMessage] = useState<string | null>(null);
  // One save at a time. It sends no key and replaces the name whole, so it's never held (R-19).
  const saves = useSubmit<ProfileUpdate>();

  async function save(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setMessage(null);
    const result = await saves.submit({
      body: () => ({ display_name: name }),
      send: ({ body }) => updateProfile(writes, body),
      keyed: false,
    });
    if (result === null) return;
    if (result.outcome === "accepted") {
      setMessage("Saved.");
      router.refresh();
      return;
    }
    setMessage(refusalText(REFUSALS, result.refusal, LOST));
  }

  return (
    <form onSubmit={(event) => void save(event)} className="space-y-3">
      <Label htmlFor="display-name" className="block">
        Display name
      </Label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          id="display-name"
          name="display_name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="nickname"
          className="sm:max-w-sm"
        />
        <Button type="submit" disabled={saves.pending}>
          Save name
        </Button>
      </div>
      <p className="text-muted-foreground text-xs">
        1 to 60 characters. Members of your workspaces can see it.
      </p>
      {message === null ? null : (
        <p role="status" data-message="profile" className="text-sm">
          {message}
        </p>
      )}
    </form>
  );
}
