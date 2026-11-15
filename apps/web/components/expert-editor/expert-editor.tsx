"use client";

import {
  getModels,
  listTools,
  type ExpertView,
  type ModelList,
  type ToolCatalog,
} from "@autobots/api-client";
import { useState } from "react";

import { ExecutorField } from "@/components/expert-editor/executor-field";
import { GrantSummary } from "@/components/expert-editor/grant-summary";
import { GroupGrants } from "@/components/expert-editor/group-grants";
import { PurposeFields } from "@/components/expert-editor/purpose-fields";
import { ToolGrants } from "@/components/expert-editor/tool-grants";
import { useExpert } from "@/components/expert-editor/use-expert";
import { useExpertDraft } from "@/components/expert-editor/use-expert-draft";
import { VersionHistory } from "@/components/expert-editor/version-history";
import { InitialTile } from "@/components/experts/initial-tile";
import { useStartSession } from "@/components/experts/use-start-session";
import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { LoadState } from "@/components/ui/load-state";
import { expansion } from "@/lib/experts/grants";
import { readOf } from "@/lib/load";
import { profileChoice } from "@/lib/model-profile";
import { useResource, type Resource } from "@/lib/use-resource";

/**
 * The editor's cards around one Expert view. A save and a session start share one message line,
 * which the suites read as `data-message="save"`.
 */
function EditorLayout({
  expert,
  catalog,
  models,
  onSaved,
}: {
  expert: ExpertView;
  catalog: Resource<ToolCatalog>;
  models: Resource<ModelList>;
  onSaved: (view: ExpertView) => void;
}) {
  const sessions = useStartSession();
  const [message, say] = useState<string | null>(null);
  const form = useExpertDraft(expert, models.value, onSaved, say);
  const { draft, setDraft, held } = form;

  async function startSession(): Promise<void> {
    const text = await sessions.start("direct", [expert.id]);
    if (text !== null) say(text);
  }

  return (
    <div className="grid items-start gap-6 @4xl:grid-cols-[minmax(0,1fr)_300px]">
      <Card aria-labelledby="config-heading" className="space-y-6 p-6">
        <div className="flex items-center gap-3">
          <InitialTile name={expert.name} className="size-10 text-lg" />
          <h2
            id="config-heading"
            className="font-serif text-[22px] leading-tight font-normal tracking-tight"
          >
            {expert.name}, version {expert.latest_version}
          </h2>
        </div>
        <form onSubmit={(event) => void form.save(event)} className="space-y-6">
          <PurposeFields draft={draft} held={held} onChange={setDraft} />
          <GroupGrants
            catalog={catalog}
            draft={draft}
            held={held}
            onChange={setDraft}
          />
          <ToolGrants
            catalog={catalog.value}
            draft={draft}
            held={held}
            onChange={setDraft}
          />
          <GrantSummary
            granted={expansion(catalog.value, draft)}
            groups={draft.groups}
          />
          <ExecutorField
            value={draft.executor}
            models={models}
            held={held}
            dropped={form.dropped}
            onChange={(value) => {
              // A value that isn't a profile is ignored (PRD-Model-Providers MP-A08).
              const executor = profileChoice(value);
              if (executor !== null) setDraft({ ...draft, executor });
            }}
          />
          {held ? <HeldNote /> : null}
          <div className="flex flex-wrap gap-2 border-t pt-5">
            <Button type="submit" disabled={form.pending}>
              Save revision
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={sessions.pending}
              onClick={() => void startSession()}
            >
              Start a session
            </Button>
          </div>
        </form>
        {message === null ? null : (
          <p role="status" data-message="save" className="text-sm">
            {message}
          </p>
        )}
      </Card>
      <VersionHistory versions={expert.versions} />
    </div>
  );
}

/**
 * One Expert's editor (US-5.1, PRD-Tool-Catalog TS-04): its purpose, instructions, granted tools and
 * model, saved as a new version, and a direct session. The Expert, the tool catalog and the models
 * are read at once, each with its own loading and unavailable states; the catalog and models
 * don't wait for the Expert, and a remount for another Expert keeps them.
 */
export function ExpertEditor({ expertId }: { expertId: string }) {
  const { read, expert, saved } = useExpert(expertId);
  const catalog = useResource(readOf(listTools));
  const models = useResource(readOf(getModels));
  if (expert === null) {
    return (
      <LoadState
        state={read.state}
        what="this Expert"
        notFound="That Expert is not available."
        onRetry={read.reload}
        pending={read.pending}
      />
    );
  }
  return (
    <EditorLayout
      key={expertId}
      expert={expert}
      catalog={catalog}
      models={models}
      onSaved={saved}
    />
  );
}
