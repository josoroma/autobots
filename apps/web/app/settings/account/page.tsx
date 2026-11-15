import type { Metadata } from "next";
import Link from "next/link";

import { AccountForm } from "@/components/account-form";
import { SignOutButton } from "@/components/sign-out-button";
import { PageHeader } from "@/components/ui/page-header";
import { SettingsSection } from "@/components/ui/section";
import { ROLE_LABEL } from "@/lib/account";
import { fetchSession, readValue } from "@/lib/service-status";

export const metadata: Metadata = { title: "Account" };

export const dynamic = "force-dynamic";

// PRD-Studio SE-04: the editable display name, the read-only email, the role and Sign out. Sign in
// shows only when signed out; a session the services can't read says so instead (WSHL-02).
export default async function AccountPage() {
  const read = await fetchSession();
  const session = readValue(read);
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Account" />
      {read.kind === "unavailable" ? (
        <div className="space-y-3">
          <p data-session="unavailable" className="text-sm">
            Your account could not be loaded. Check that the local services are
            running, then reload.
          </p>
          {/* Signing out needs only the sign-in service (PRD-Studio SH-05). */}
          <SignOutButton />
        </div>
      ) : session === null ? (
        <p className="text-sm">
          <Link href="/sign-in" className="font-medium underline">
            Sign in
          </Link>{" "}
          to manage your account.
        </p>
      ) : (
        <>
          <SettingsSection
            id="name-heading"
            title="Name"
            description="Shown in the sidebar and greetings."
            layout="wide"
          >
            <AccountForm
              initial={session.display_name_saved ? session.display_name : ""}
            />
          </SettingsSection>
          <SettingsSection
            id="identity-heading"
            title="Sign-in and role"
            layout="wide"
          >
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
                    {ROLE_LABEL[workspace.role]}
                  </dd>
                </div>
              ))}
            </dl>
          </SettingsSection>
          <div className="border-border border-t pt-5">
            <SignOutButton />
          </div>
        </>
      )}
    </div>
  );
}
