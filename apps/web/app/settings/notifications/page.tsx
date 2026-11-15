import type { Metadata } from "next";

import { NotificationsControl } from "@/components/notifications-control";
import { PageHeader } from "@/components/ui/page-header";
import { SettingsSection } from "@/components/ui/section";

export const metadata: Metadata = { title: "Notifications" };

export default function NotificationsPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Notifications" />
      <SettingsSection
        id="notify-heading"
        title="Browser notifications"
        description="Stored in this browser, with the browser's permission."
      >
        <NotificationsControl />
      </SettingsSection>
    </div>
  );
}
