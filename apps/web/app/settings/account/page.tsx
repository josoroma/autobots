import Link from "next/link";

import { AccountForm } from "@/components/account-form";
import { SignOutButton } from "@/components/sign-out-button";
import { PageHeader } from "@/components/ui/page-header";
import { fetchSession, readValue } from "@/lib/service-status";

export const dynamic = "force-dynamic";

const ROLE = { owner: "Owner", member: "Member" } as const;

// PRD-Studio SE-04: the editable display name, the read-only email, the role and Sign out. Sign in
// shows only when signed out; a session the services can't read says so instead (WSHL-02).
export default async function AccountPage() {
  const read = await fetchSession();
  const session = readValue(read);
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Account" />
      {read.kind === "unavailable" ? (
        <p data-session="unavailable" className="text-sm">
          Your account could not be loaded. Check that the local services are
          running, then reload.
        </p>
      ) : session === null ? (
        <p className="text-sm">
          <Link href="/sign-in" className="font-medium underline">
            Sign in
          </Link>{" "}
          to manage your account.
        </p>
      ) : (
        <>
          <section
            aria-labelledby="name-heading"
            className="border-border grid gap-4 border-t pt-5 md:grid-cols-[260px_1fr]"
          >
            <div>
              <h2 id="name-heading" className="text-sm font-semibold">
                Name
              </h2>
              <p className="text-muted-foreground text-[13px]">
                Shown in the sidebar and greetings.
              </p>
            </div>
            <AccountForm
              initial={session.display_name_saved ? session.display_name : ""}
            />
          </section>
          <section
            aria-labelledby="identity-heading"
            className="border-border grid gap-4 border-t pt-5 md:grid-cols-[260px_1fr]"
          >
            <h2 id="identity-heading" className="text-sm font-semibold">
              Sign-in and role
            </h2>
            <dl className="grid grid-cols-[7rem_minmax(0,1fr)] gap-y-2 text-sm">
              <dt className="text-muted-foreground">Email</dt>
              <dd data-field="email" className="wrap-anywhere">
                {session.email ?? "Not available"}
              </dd>
              {session.workspaces.map((workspace) => (
                <div key={workspace.id} className="contents">
                  <dt className="text-muted-foreground wrap-anywhere">
                    {workspace.name}
                  </dt>
                  <dd data-workspace-role={workspace.id}>
                    {ROLE[workspace.role]}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
          <div className="border-border border-t pt-5">
            <SignOutButton />
          </div>
        </>
      )}
    </div>
  );
}
