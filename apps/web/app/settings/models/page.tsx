import type { Metadata } from "next";
import Link from "next/link";

import { ModelPolicyPanel } from "@/components/model-policy/model-policy-panel";
import { ModelSourcePanel } from "@/components/model-source/model-source-panel";
import { ProviderSettingsPanel } from "@/components/provider-settings/provider-settings-panel";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Models" };

// The page owns its navigation, so the link back to Home's draft sits between the provider and the
// policy whatever either panel shows (WSYS-07). Model source sits above both (Decision 0041 A13).
export default function ModelSettingsPage() {
  return (
    <div className="max-w-5xl space-y-8">
      <PageHeader title="Models" />
      <ModelSourcePanel />
      <ProviderSettingsPanel />
      <Link href="/" className="inline-block text-sm font-medium underline">
        Return to your draft
      </Link>
      <ModelPolicyPanel />
    </div>
  );
}
