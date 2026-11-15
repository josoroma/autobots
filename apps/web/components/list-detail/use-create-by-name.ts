/**
 * Creating a named item, an Expert or a workflow, then opening it (US-5.1, US-6.3). One key per
 * intent until its outcome is known, so a double press or a lost reply creates one, and while the
 * write is held its name stays as sent (Decision 0027 D2). The screen shows the message, which its
 * other writes may share.
 */
import type { ClientOptions } from "@autobots/api-client/runtime";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { writes } from "@/lib/api/browser";
import { createText } from "@/lib/studio-writes";
import { useSubmit } from "@/lib/use-submit";

export interface CreateSteps<B, T extends { id: string }> {
  /** The generated create, such as `createExpert`, which parses its reply. */
  operation: (
    options: ClientOptions,
    body: B,
    headers: { "Idempotency-Key": string },
  ) => Promise<T>;
  body: (name: string) => B;
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

export function useCreateByName<B, T extends { id: string }>(
  steps: CreateSteps<B, T>,
  say: (message: string | null) => void,
): CreateByName {
  const creates = useSubmit<B>();
  const router = useRouter();
  const [name, setName] = useState("");

  async function create(event: FormEvent): Promise<void> {
    event.preventDefault();
    say(null);
    const result = await creates.submit({
      body: () => steps.body(name),
      send: ({ key, body }) =>
        steps.operation(writes, body, { "Idempotency-Key": key }),
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
