import Link from "next/link";

import { AboutServices } from "@/components/about-services";
import { GoalComposer } from "@/components/goal-composer";
import { ServiceStatusBadge } from "@/components/service-status-badge";
import { SignOutButton } from "@/components/sign-out-button";
import { Card } from "@/components/ui/card";
import { fetchServiceStatus, fetchSession } from "@/lib/service-status";

// The status is read per request, on the server, so it is never baked into a build.
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [status, session] = await Promise.all([
    fetchServiceStatus(),
    fetchSession(),
  ]);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Local workbench</h1>
      <Card aria-labelledby="account-heading" className="space-y-3">
        <h2 id="account-heading" className="text-lg font-medium">
          Account
        </h2>
        {session === null ? (
          <>
            <p className="text-sm" data-session="signed-out">
              You are not signed in.
            </p>
            <Link href="/sign-in" className="text-sm font-medium underline">
              Sign in
            </Link>
          </>
        ) : (
          <>
            <p className="text-sm" data-session="signed-in">
              Signed in, with access to {session.workspace_ids.length} workspace
              {session.workspace_ids.length === 1 ? "" : "s"}.
            </p>
            <SignOutButton />
          </>
        )}
      </Card>
      <GoalComposer />
      <Card aria-labelledby="services-heading" className="space-y-3">
        <h2 id="services-heading" className="text-lg font-medium">
          Services
        </h2>
        <p className="text-muted-foreground text-sm">
          The app and your data stay on this Mac. Model calls go to OpenRouter,
          and this page makes none.
        </p>
        <ServiceStatusBadge status={status} />
        <AboutServices />
      </Card>
    </div>
  );
}
