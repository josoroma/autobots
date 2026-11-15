import type { Metadata } from "next";
import { Suspense } from "react";

import { SessionPanel } from "@/components/session-panel";
import { LoadState, ServerLoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { readWorkSession } from "@/lib/server-api";

export const metadata: Metadata = { title: "Session" };

const LOADING = { kind: "loading" } as const;

async function Session({ sessionId }: { sessionId: string }) {
  const read = await readWorkSession(sessionId);
  return read.kind === "ready" ? (
    <SessionPanel session={read.value} />
  ) : (
    <ServerLoadState
      state={read}
      what="this session"
      notFound="That session is not available."
    />
  );
}

// The session is read on the server and streams in below the title (R-67).
export default async function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="@container max-w-4xl space-y-8">
      <PageHeader title="Session" />
      <Suspense fallback={<LoadState state={LOADING} what="this session" />}>
        <Session sessionId={id} />
      </Suspense>
    </div>
  );
}
