/**
 * The composer's chips (PRD-Studio HM-02): the offered models and the Experts, each read once, and
 * the person's model, Expert and budget choices. A list that can't be read offers only its default.
 */
import {
  getModels,
  listExperts,
  type ExpertView,
  type ModelAvailability,
  type ModelProfileId,
} from "@autobots/api-client";
import { useState } from "react";

import { readOf } from "@/lib/load";
import { useResource } from "@/lib/use-resource";

/** The Expert choice for a goal run, which starts no session. */
export const NO_EXPERT = "";

export interface RunOptions {
  /** The models new runs may use, from ModelAvailability.offered. */
  models: readonly ModelAvailability[];
  experts: readonly ExpertView[];
  /** The chosen profile, or "" for the workspace setting. */
  profile: string;
  chooseProfile: (profile: string) => void;
  expertId: string;
  chooseExpert: (expertId: string) => void;
  /** The chosen Expert's role bindings at its latest version, which a run-wide choice doesn't replace. */
  roleOverrides: Readonly<Record<string, ModelProfileId>> | undefined;
  /** The budget picked, or null for the server's default. */
  chosenBudget: number | null;
  chooseBudget: (budget: number) => void;
}

export function useRunOptions(): RunOptions {
  const expertRead = useResource(readOf(listExperts));
  const modelRead = useResource(readOf(getModels));
  const [profile, chooseProfile] = useState("");
  const [expertId, chooseExpert] = useState(NO_EXPERT);
  const [chosenBudget, setChosenBudget] = useState<number | null>(null);
  const experts = expertRead.value?.experts ?? [];
  const expert = experts.find((item) => item.id === expertId) ?? null;
  return {
    models: (modelRead.value?.models ?? []).filter((model) => model.offered),
    experts,
    profile,
    chooseProfile,
    expertId,
    chooseExpert,
    roleOverrides: expert?.versions.find(
      (version) => version.version === expert.latest_version,
    )?.config.role_bindings,
    chosenBudget,
    chooseBudget: setChosenBudget,
  };
}
