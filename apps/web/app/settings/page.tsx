import type { Metadata } from "next";

import { AppearanceControl } from "@/components/appearance-control";
import { PageHeader } from "@/components/ui/page-header";
import { SettingsSection } from "@/components/ui/section";

export const metadata: Metadata = { title: "Settings" };

// PRD-Studio SE-03 (Decision 0022): Appearance offers System, serif documents, density and reduced motion.
export default function SettingsPage() {
  return (
    <div className="max-w-3xl space-y-8">
      <PageHeader title="Settings" />
      <SettingsSection
        id="appearance-heading"
        title="Appearance"
        description="These choices are stored in this browser. They change presentation only, never a run, an approval or a workflow."
      >
        <AppearanceControl />
      </SettingsSection>
    </div>
  );
}
