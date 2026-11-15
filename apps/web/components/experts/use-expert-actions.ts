/**
 * The Experts list's writes (WBLD-12): a direct session from a card, a coordinator session among the
 * Experts chosen, and a new Expert. Session starts share one write at a time; each says why it
 * didn't open in the create section's message, as a create does.
 */
import { parseExpertView } from "@autobots/api-client";
import { useState } from "react";

import { useStartSession } from "@/components/experts/use-start-session";
import {
  useCreateByName,
  type CreateByName,
} from "@/components/list-detail/use-create-by-name";

const CREATE_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can create an Expert.",
  expert_name_taken: "That name is already used.",
};
// The coordinator session's target, whose Experts are its body.
const COORDINATOR = "coordinator";

export interface ExpertActions {
  message: string | null;
  /** The Experts chosen for a coordinator session. */
  routed: ReadonlySet<string>;
  toggle: (expertId: string) => void;
  startRun: (expertId: string) => Promise<void>;
  coordinate: () => Promise<void>;
  /** A session start is pending. */
  starting: boolean;
  /** A coordinator session is held, so the Experts it names stay as sent (Decision 0027 D2). */
  routing: boolean;
  create: CreateByName;
}

export function useExpertActions(): ExpertActions {
  const sessions = useStartSession();
  const [message, setMessage] = useState<string | null>(null);
  const [routed, setRouted] = useState<ReadonlySet<string>>(() => new Set());
  const create = useCreateByName(
    {
      endpoint: "/api/v1/experts",
      body: (name) => ({ name, config: {} }),
      parse: parseExpertView,
      hrefFor: (expert) => `/experts/${expert.id}`,
      refusals: CREATE_REFUSALS,
    },
    setMessage,
  );

  async function startRun(expertId: string): Promise<void> {
    const text = await sessions.start("direct", [expertId], expertId);
    if (text !== null) setMessage(text);
  }

  async function coordinate(): Promise<void> {
    const text = await sessions.start("coordinator", [...routed], COORDINATOR);
    if (text !== null) setMessage(text);
  }

  function toggle(expertId: string): void {
    setRouted((current) => {
      const next = new Set(current);
      if (next.has(expertId)) next.delete(expertId);
      else next.add(expertId);
      return next;
    });
  }

  return {
    message,
    routed,
    toggle,
    startRun,
    coordinate,
    starting: sessions.pending,
    routing: sessions.holding(COORDINATOR),
    create,
  };
}
