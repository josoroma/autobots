"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";

// PRD-Studio SE-04 and ID-01: edit only your own display name. The API refuses an empty or
// overlong name with display_name_invalid, and the saved name stays as it was.
export function AccountForm({ initial }: { initial: string }) {
  const router = useRouter();
  const [name, setName] = useState(initial);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const reply = await csrfFetch("/api/v1/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: name }),
      });
      if (reply.ok) {
        setMessage("Saved.");
        router.refresh();
        return;
      }
      const body = (await reply.json().catch(() => null)) as {
        code?: string;
      } | null;
      setMessage(
        body?.code === "display_name_invalid"
          ? "A display name needs 1 to 60 characters. Nothing changed."
          : "That did not save. Nothing changed.",
      );
    } catch {
      setMessage("That did not save. Nothing changed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={(event) => void save(event)} className="space-y-3">
      <label htmlFor="display-name" className="block text-sm font-medium">
        Display name
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          id="display-name"
          name="display_name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="nickname"
          className="sm:max-w-sm"
        />
        <Button type="submit" disabled={busy}>
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
