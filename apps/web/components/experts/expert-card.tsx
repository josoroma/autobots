import type { ExpertView } from "@autobots/api-client";
import { ShieldAlert } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, InitialTile } from "@/components/ui/card";
import { Choice } from "@/components/ui/field";
import {
  approvalNote,
  browseDomainsLine,
  executorLine,
  initialOf,
  runsLine,
  toolChips,
  type CatalogTools,
} from "@/lib/experts/card";

const CHIP =
  "text-muted-foreground rounded-md border px-1.5 py-px font-mono text-tag wrap-anywhere";

/** The first tools a version grants, how many more, and its groups. */
function ToolChips({ chips }: { chips: readonly string[] }) {
  return (
    <div className="mt-auto flex flex-wrap gap-1.5 border-t pt-3">
      {chips.map((chip) => (
        <span key={chip} className={CHIP}>
          {chip}
        </span>
      ))}
    </div>
  );
}

/** One Expert as a card: what its latest version says, from the list already loaded (WBLD-12). */
export function ExpertCard({
  expert,
  tools,
  now,
  checked,
  locked,
  busy,
  onToggle,
  onStart,
}: {
  expert: ExpertView;
  /** The catalog's tools, or null until it's read. */
  tools: CatalogTools | null;
  /** When the list was read, in epoch milliseconds. */
  now: number;
  checked: boolean;
  /** A held coordinator session names these Experts, so they stay as sent. */
  locked: boolean;
  busy: boolean;
  onToggle: () => void;
  onStart: () => void;
}) {
  const latest = expert.versions.at(-1)?.config ?? {};
  const purpose = latest.purpose?.trim() ?? "";
  const approval = approvalNote(latest.tools ?? [], tools);
  const browsing = browseDomainsLine(latest);
  return (
    <Card
      as="li"
      className="has-checked:border-primary/60 has-checked:ring-primary/15 flex flex-col gap-3 p-[18px] has-checked:ring-3"
    >
      <div className="flex items-start gap-3">
        <InitialTile
          initial={initialOf(expert.name)}
          className="size-9 text-base"
        />
        <div className="min-w-0 flex-1">
          <Link
            href={`/experts/${expert.id}`}
            className="text-lead font-semibold wrap-anywhere underline-offset-4 hover:underline"
          >
            {expert.name}
          </Link>
          <p
            data-field="role"
            className="text-muted-foreground font-mono text-tag wrap-anywhere"
          >
            {executorLine(expert)}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          disabled={busy}
          onClick={onStart}
        >
          Start run
          <span className="sr-only"> with {expert.name}</span>
        </Button>
        <Choice
          type="checkbox"
          id={`route-${expert.id}`}
          checked={checked}
          disabled={locked}
          onChange={onToggle}
          aria-label={`Include ${expert.name} in a coordinator session`}
          className="mt-0.5 shrink-0"
        />
      </div>
      {purpose === "" ? null : (
        <p className="text-muted-foreground text-body leading-normal">
          {purpose}
        </p>
      )}
      <p data-field="runs" className="text-muted-foreground text-meta">
        {runsLine(expert, now)}
      </p>
      {approval === null ? null : (
        <p
          data-field="approval"
          className="text-attention flex items-center gap-1.5 text-meta"
        >
          <ShieldAlert aria-hidden="true" className="size-3.5" />
          {approval}
        </p>
      )}
      {browsing === null ? null : (
        <p
          data-field="browse-domains"
          className="text-muted-foreground text-meta break-words"
        >
          {browsing}
        </p>
      )}
      <ToolChips chips={toolChips(latest)} />
    </Card>
  );
}
