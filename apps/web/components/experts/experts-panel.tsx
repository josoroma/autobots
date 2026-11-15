"use client";

import { useState } from "react";

import { CoordinatorBar } from "@/components/experts/coordinator-bar";
import { ExpertCard } from "@/components/experts/expert-card";
import { ExpertFilters } from "@/components/experts/expert-filters";
import { useExpertActions } from "@/components/experts/use-expert-actions";
import { useExpertList } from "@/components/experts/use-expert-list";
import { CreateByName } from "@/components/list-detail/create-by-name";
import { ListSection } from "@/components/list-detail/list-section";
import { LoadState } from "@/components/ui/load-state";
import {
  EXPERT_FILTER_IDS,
  inExpertFilter,
  type ExpertFilter,
} from "@/lib/experts/card";
import { filterList, tabCounts } from "@/lib/list-filter";

/**
 * The Experts list (US-5.1, PRD-Studio EX-01 to EX-03): cards with their class and approval note,
 * a filter and search, direct and coordinator sessions, and a new Expert. Each read says why it
 * failed, and the catalog's own failure offers Retry beside the filters it holds back.
 */
export function ExpertsPanel() {
  const data = useExpertList();
  const actions = useExpertActions();
  const [filter, setFilter] = useState<ExpertFilter>("all");
  const [search, setSearch] = useState("");

  if (data.experts === null) {
    return (
      <LoadState
        state={data.list.state}
        what="Experts"
        onRetry={data.list.reload}
        pending={data.list.pending}
      />
    );
  }
  const shown = filterList(
    data.classified,
    { tab: filter, search },
    inExpertFilter,
    (item) => item.expert.name,
  );
  return (
    <>
      <ListSection
        heading="Your Experts"
        className="space-y-4"
        toolbar={
          <>
            <ExpertFilters
              filter={filter}
              onFilter={setFilter}
              counts={tabCounts(
                data.classified,
                EXPERT_FILTER_IDS,
                inExpertFilter,
              )}
              known={data.tools !== null}
              search={search}
              onSearch={setSearch}
            />
            {data.tools !== null ||
            data.catalog.state.kind === "loading" ? null : (
              <LoadState
                state={data.catalog.state}
                what="the tool catalog"
                onRetry={data.catalog.reload}
                pending={data.catalog.pending}
              />
            )}
          </>
        }
        total={data.experts.length}
        shown={shown.length}
        empty="No Experts yet."
        noMatch="No Experts match."
        footer={
          <CoordinatorBar
            routing={actions.routing}
            disabled={actions.routed.size === 0 || actions.starting}
            onStart={() => void actions.coordinate()}
          />
        }
      >
        <ul className="grid gap-3.5 @xl:grid-cols-2 @4xl:grid-cols-3">
          {shown.map(({ expert }) => (
            <ExpertCard
              key={expert.id}
              expert={expert}
              tools={data.tools}
              now={data.now}
              checked={actions.routed.has(expert.id)}
              locked={actions.routing}
              busy={actions.starting}
              onToggle={() => actions.toggle(expert.id)}
              onStart={() => void actions.startRun(expert.id)}
            />
          ))}
        </ul>
      </ListSection>
      <CreateByName
        heading="New Expert"
        inputId="expert-name"
        create={actions.create}
        message={actions.message}
      />
    </>
  );
}
