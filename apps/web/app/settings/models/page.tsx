import { ModelPolicyPanel } from "@/components/model-policy-panel";
import { ProviderSettingsPanel } from "@/components/provider-settings-panel";
import { PageHeader } from "@/components/ui/page-header";

export default function ModelSettingsPage() {
  return (
    <div className="max-w-5xl space-y-8">
      <PageHeader title="Models" />
      <ProviderSettingsPanel />
      <ModelPolicyPanel />
    </div>
  );
}
