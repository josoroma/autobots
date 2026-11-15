import Link from "next/link";

import { ModelPolicyPanel } from "@/components/model-policy/model-policy-panel";
import { ProviderSettingsPanel } from "@/components/provider-settings/provider-settings-panel";
import { PageHeader } from "@/components/ui/page-header";

// The page owns its navigation, so the link back to Home's draft sits between the provider and the
// policy whatever either panel shows (WSYS-07).
export default function ModelSettingsPage() {
  return (
    <div className="max-w-5xl space-y-8">
      <PageHeader title="Models" />
      <ProviderSettingsPanel />
      <Link href="/" className="inline-block text-sm font-medium underline">
        Return to your draft
      </Link>
      <ModelPolicyPanel />
    </div>
  );
}
