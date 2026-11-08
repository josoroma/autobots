import type { Metadata } from "next";

import { NotificationsControl } from "@/components/notifications-control";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Notifications" };

export default function NotificationsPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Notifications" />
      <section
        aria-labelledby="notify-heading"
        className="border-border grid gap-4 border-t pt-5 md:grid-cols-[minmax(0,240px)_minmax(0,1fr)] md:gap-7"
      >
        <div className="space-y-1">
          <h2 id="notify-heading" className="text-sm font-semibold">
            Browser notifications
          </h2>
          <p className="text-muted-foreground text-[12.5px] leading-relaxed">
            Stored in this browser, with the browser&apos;s permission.
          </p>
        </div>
        <NotificationsControl />
      </section>
    </div>
  );
}
