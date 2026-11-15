"use client";

import { ApprovedModels } from "@/components/model-policy/approved-models";
import { PolicyForm } from "@/components/model-policy/policy-form";
import {
  NotOfferedAlert,
  RoleEffect,
} from "@/components/model-policy/role-effect";
import { usePolicyDraft } from "@/components/model-policy/use-policy-draft";
import { usePolicyRead } from "@/components/model-policy/use-policy-read";
import { usePolicyWrites } from "@/components/model-policy/use-policy-writes";
import { LoadState } from "@/components/ui/load-state";
import { POLICY_DISCARDED, savedChoiceNotOffered } from "@/lib/model-policy";

// PRD-Studio MD-01 to MD-03: the approved models with their catalog facts, what the saved policy
// does, and the form that changes it. Every write sends the version this screen loaded.
export function ModelPolicyPanel() {
  const read = usePolicyRead();
  const policy = usePolicyDraft(read.policy);
  const writes = usePolicyWrites(policy.adopt);
  const { saved, draft } = policy;
  if (read.models === null || saved === null || draft === null) {
    return (
      <LoadState
        state={read.state}
        what="models"
        onRetry={read.retry}
        pending={read.pending}
      />
    );
  }
  const models = read.models.models;
  return (
    <section aria-labelledby="policy-heading" className="space-y-5">
      <h2 id="policy-heading" className="text-sm font-semibold">
        Approved models and role policy
      </h2>
      <ApprovedModels models={read.models} />
      <RoleEffect state={saved} />
      {savedChoiceNotOffered(saved, models) ? <NotOfferedAlert /> : null}
      <PolicyForm
        models={models}
        saved={saved}
        draft={draft}
        dirty={policy.dirty}
        pending={writes.pending}
        onDefault={policy.setDefault}
        onOverride={policy.setOverride}
        onSave={() => void writes.save(saved, draft)}
        onDiscard={() => {
          policy.adopt(saved);
          writes.say(POLICY_DISCARDED);
        }}
        onReset={() => void writes.reset(saved)}
      />
      {writes.message === null ? null : (
        <p
          role="status"
          data-policy-message="true"
          aria-live="polite"
          className="text-sm font-medium"
        >
          {writes.message}
        </p>
      )}
    </section>
  );
}
