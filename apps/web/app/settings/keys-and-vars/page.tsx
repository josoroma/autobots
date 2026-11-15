import { KeysAndVarsPanel } from "@/components/keys-and-vars/keys-and-vars-panel";
import { PageHeader } from "@/components/ui/page-header";

export default function KeysAndVarsSettingsPage() {
  return (
    <div className="max-w-3xl space-y-8">
      <PageHeader title="Keys & vars" />
      <KeysAndVarsPanel />
    </div>
  );
}
