import { ModelPolicyPanel } from "@/components/model-policy-panel";
import { ProviderSettingsPanel } from "@/components/provider-settings-panel";

export default function ModelSettingsPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Models</h1>
      <ProviderSettingsPanel />
      <ModelPolicyPanel />
    </div>
  );
}
