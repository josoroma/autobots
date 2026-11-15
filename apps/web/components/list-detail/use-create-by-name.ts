/**
 * Creating a named item, an Expert or a workflow, then opening it (US-5.1, US-6.3). One key per
 * intent until its outcome is known, so a double press or a lost reply creates one, and while the
 * write is held its name stays as sent (Decision 0027 D2). The screen shows the message, which its
 * other writes may share.
 */
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { csrfFetch } from "@/lib/csrf-fetch";
import { createText } from "@/lib/studio-writes";
import { useSubmit } from "@/lib/use-submit";

export interface CreateSteps<T extends { id: string }> {
  /** The collection the create posts to, such as `/api/v1/experts`. */
  endpoint: string;
  body: (name: string) => unknown;
  parse: (value: unknown) => T;
  /** Where the created item opens. */
  hrefFor: (created: T) => string;
  /** The screen's words for each refusal code. */
  refusals: Readonly<Record<string, string>>;
}

export interface CreateByName {
  name: string;
  setName: (name: string) => void;
  create: (event: FormEvent) => Promise<void>;
  pending: boolean;
  /** A create is held, so its name stays as sent. */
  held: boolean;
}

export function useCreateByName<T extends { id: string }>(
  steps: CreateSteps<T>,
  say: (message: string | null) => void,
): CreateByName {
  const creates = useSubmit();
  const router = useRouter();
  const [name, setName] = useState("");

  async function create(event: FormEvent): Promise<void> {
    event.preventDefault();
    say(null);
    const result = await creates.submit({
      body: () => JSON.stringify(steps.body(name)),
      send: ({ key, body }) =>
        csrfFetch(steps.endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: steps.parse,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      router.push(steps.hrefFor(result.value));
      return;
    }
    say(createText(result, steps.refusals));
  }

  return {
    name,
    setName,
    create,
    pending: creates.pending,
    held: creates.holding(),
  };
}
