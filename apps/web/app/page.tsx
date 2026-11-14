import { chosenWorkspace, currentWorkspace } from "@/lib/workspace-choice";
import type { SessionSummary } from "@autobots/api-client";
import { Server, UserRound } from "lucide-react";
import Link from "next/link";

import { AboutServices } from "@/components/about-services";
import { GoalComposer } from "@/components/goal-composer";
import { HomeActivity } from "@/components/home-activity";
import { HomeGreeting } from "@/components/home-greeting";
import { ServiceChips } from "@/components/readiness";
import { ServiceStatusBadge } from "@/components/service-status-badge";
import { SignOutButton } from "@/components/sign-out-button";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { SectionLabel } from "@/components/ui/page-header";
import {
  fetchReadiness,
  fetchServiceStatus,
  fetchSession,
  readValue,
  type MemberRead,
} from "@/lib/service-status";
import { cn } from "@/lib/utils";

// The status is read per request, on the server, so it is never baked into a build.
export const dynamic = "force-dynamic";

// Decision 0021: the two lower sections are quiet hairline lists. They share a row and end in their one
// action at the same height, so Tab never climbs from one to the next.
const LOWER_SECTION = "flex min-w-0 flex-col";
const LOWER_HEAD = "mb-2 flex items-center gap-2";
const LOWER_ITEM = "border-t py-3 text-sm";
const LOWER_ACTION = "mt-auto pt-2";

// Sign in shows only when signed out; a session the services can't read says so instead (WSHL-02).
const ACCOUNT_BADGE = {
  ok: { variant: "success", words: "Signed in" },
  signed_out: { variant: "muted", words: "Signed out" },
  unavailable: { variant: "attention", words: "Unavailable" },
} as const;

function AccountState({ read }: { read: MemberRead<SessionSummary> }) {
  if (read.kind === "ok") {
    const count = read.value.workspace_ids.length;
    return (
      <p data-session="signed-in">
        Signed in, with access to {count} workspace{count === 1 ? "" : "s"}.
      </p>
    );
  }
  return read.kind === "signed_out" ? (
    <p data-session="signed-out">You are not signed in.</p>
  ) : (
    <p data-session="unavailable">
      Your session could not be checked. Check that the local services are
      running, then reload.
    </p>
  );
}

function AccountAction({ read }: { read: MemberRead<SessionSummary> }) {
  if (read.kind === "ok") return <SignOutButton />;
  return read.kind === "signed_out" ? (
    <Link
      href="/sign-in"
      className={buttonVariants({ variant: "outline", size: "sm" })}
    >
      Sign in
    </Link>
  ) : null;
}

export default async function HomePage() {
  const [status, read, readiness, chosen] = await Promise.all([
    fetchServiceStatus(),
    fetchSession(),
    fetchReadiness(),
    chosenWorkspace(),
  ]);
  const session = readValue(read);
  const badge = ACCOUNT_BADGE[read.kind];
  return (
    <div className="mx-auto w-full max-w-[780px] md:pt-10">
      <header className="mb-8 space-y-3 text-center">
        {session === null ? null : (
          <HomeGreeting
            name={session.display_name}
            timeZone={
              currentWorkspace(session.workspaces, chosen)?.timezone ?? "UTC"
            }
          />
        )}
        <h1 className="text-4xl leading-[1.1] md:text-[44px]">
          What should we work on?
        </h1>
        <p className="text-muted-foreground mx-auto max-w-xl text-[15px]">
          Start a goal, see what it would use, and check the services on this
          Mac.
        </p>
      </header>
      <GoalComposer />
      {session === null ? null : <HomeActivity />}
      <div className="mt-14 grid gap-10 md:grid-cols-2 md:gap-8">
        <section aria-labelledby="account-heading" className={LOWER_SECTION}>
          <div className={LOWER_HEAD}>
            <UserRound
              aria-hidden="true"
              className="text-muted-foreground size-3.5 shrink-0"
            />
            <SectionLabel id="account-heading" className="text-[12.5px]">
              Account
            </SectionLabel>
            <Badge variant={badge.variant} dot className="ml-auto">
              {badge.words}
            </Badge>
          </div>
          <div className={LOWER_ITEM}>
            <AccountState read={read} />
          </div>
          <div className={LOWER_ACTION}>
            <AccountAction read={read} />
          </div>
        </section>
        <section aria-labelledby="services-heading" className={LOWER_SECTION}>
          <div className={LOWER_HEAD}>
            <Server
              aria-hidden="true"
              className="text-muted-foreground size-3.5 shrink-0"
            />
            <SectionLabel id="services-heading" className="text-[12.5px]">
              Services
            </SectionLabel>
          </div>
          <p className={cn(LOWER_ITEM, "text-muted-foreground")}>
            The app and your data stay on this Mac. Model calls go to
            OpenRouter, and this page makes none.
          </p>
          <div className={LOWER_ITEM}>
            <ServiceStatusBadge status={status} />
            {readiness.kind === "ok" ? (
              <ServiceChips readiness={readiness.value} />
            ) : null}
          </div>
          <div className={LOWER_ACTION}>
            <AboutServices />
          </div>
        </section>
      </div>
    </div>
  );
}
