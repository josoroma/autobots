import { Server, UserRound } from "lucide-react";
import Link from "next/link";

import { AboutServices } from "@/components/about-services";
import { GoalComposer } from "@/components/goal-composer";
import { ServiceStatusBadge } from "@/components/service-status-badge";
import { SignOutButton } from "@/components/sign-out-button";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  IconTile,
} from "@/components/ui/card";
import { fetchServiceStatus, fetchSession } from "@/lib/service-status";

// The status is read per request, on the server, so it is never baked into a build.
export const dynamic = "force-dynamic";

// The two small cards share a row and end in their one action, at the same height, so Tab never climbs.
const SMALL_CARD = "flex flex-col gap-5";

export default async function HomePage() {
  const [status, session] = await Promise.all([
    fetchServiceStatus(),
    fetchSession(),
  ]);
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">
          Local workbench
        </h1>
        <p className="text-muted-foreground text-sm">
          Start a goal, see what it would use, and check the services on this
          Mac.
        </p>
      </header>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card aria-labelledby="account-heading" className={SMALL_CARD}>
          <CardHeader>
            <IconTile icon={UserRound} />
            <div className="min-w-0 flex-1 space-y-1">
              <CardTitle id="account-heading">Account</CardTitle>
              {session === null ? (
                <CardDescription data-session="signed-out">
                  You are not signed in.
                </CardDescription>
              ) : (
                <CardDescription data-session="signed-in">
                  Signed in, with access to {session.workspace_ids.length}{" "}
                  workspace
                  {session.workspace_ids.length === 1 ? "" : "s"}.
                </CardDescription>
              )}
            </div>
            <Badge variant={session === null ? "outline" : "secondary"} dot>
              {session === null ? "Signed out" : "Signed in"}
            </Badge>
          </CardHeader>
          <div className="mt-auto">
            {session === null ? (
              <Link
                href="/sign-in"
                className={buttonVariants({ className: "w-full" })}
              >
                Sign in
              </Link>
            ) : (
              <SignOutButton className="w-full" />
            )}
          </div>
        </Card>
        <Card aria-labelledby="services-heading" className={SMALL_CARD}>
          <CardHeader>
            <IconTile icon={Server} />
            <div className="min-w-0 flex-1 space-y-1">
              <CardTitle id="services-heading">Services</CardTitle>
              <CardDescription>
                The app and your data stay on this Mac. Model calls go to
                OpenRouter, and this page makes none.
              </CardDescription>
            </div>
          </CardHeader>
          <ServiceStatusBadge status={status} />
          <div className="mt-auto">
            <AboutServices className="w-full" />
          </div>
        </Card>
      </div>
      <GoalComposer />
    </div>
  );
}
