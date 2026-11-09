import { ToolKeysPanel } from "@/components/tool-keys-panel";
import { PageHeader } from "@/components/ui/page-header";

export default function ToolKeysSettingsPage() {
  return (
    <div className="max-w-3xl space-y-8">
      <PageHeader title="Tool keys" />
      <ToolKeysPanel />
    </div>
  );
}
