"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import { ModelPolicyPanel } from "@/components/model-policy/model-policy-panel";
import { ModelSourcePanel } from "@/components/model-source/model-source-panel";

// Model source and the policy are one stored row with one version (Decision 0041 A1, MP-05). A
// switch changes which profiles the policy lists and what its default saves (A8), and a save moves
// the version a switch must send, so each panel reads again, from a new mount, after the other's
// accepted write. `children` sit between the two panels, as the page places them.
export function ModelPanels({ children }: { children: ReactNode }) {
  const [switches, setSwitches] = useState(0);
  const [saves, setSaves] = useState(0);
  return (
    <>
      <ModelSourcePanel
        key={saves}
        onSwitched={() => setSwitches((count) => count + 1)}
      />
      {children}
      <ModelPolicyPanel
        key={switches}
        onSaved={() => setSaves((count) => count + 1)}
      />
    </>
  );
}
