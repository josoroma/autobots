import type { Metadata } from "next";

import { BrowsingPanel } from "@/components/settings/browsing-panel";
import { PageHeader } from "@/components/ui/page-header";
import { SettingsSection } from "@/components/ui/section";

export const metadata: Metadata = { title: "Browsing" };

// Decision 0035 Y1: the workspace's YOLO setting for browse_goal.
export default function BrowsingSettingsPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Browsing" />
      <SettingsSection
        id="browsing-heading"
        title="Typing and submitting"
        description="Stored for the workspace. Every member sees it; only the owner changes it."
      >
        <BrowsingPanel />
      </SettingsSection>
    </div>
  );
}
