"use client";

import {
  getBrowsingSettings,
  markBrowsingNoticeSeen,
} from "@autobots/api-client";
import { Globe } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

import { writes as writeClient } from "@/lib/api/browser";
import { readOf } from "@/lib/load";
import { useResource } from "@/lib/use-resource";

const READ = readOf(getBrowsingSettings);

// Decision 0035 Y1: once, the owner learns that browsing's YOLO setting is on. Showing the notice
// marks it seen, so the next visit to Home shows nothing. Members never see it.
export function BrowsingNotice() {
  const read = useResource(READ);
  const pending = read.value?.notice_pending === true;
  const marked = useRef(false);
  useEffect(() => {
    if (!pending || marked.current) return;
    marked.current = true;
    void markBrowsingNoticeSeen(writeClient).catch(() => undefined);
  }, [pending]);
  if (!pending) return null;
  return (
    <div
      role="status"
      data-field="browsing-notice"
      className="border-border bg-card mt-6 flex items-start gap-3 rounded-lg border px-4 py-3 text-ui"
    >
      <Globe
        aria-hidden="true"
        className="text-muted-foreground mt-0.5 size-4"
      />
      <p className="leading-relaxed">
        Browsing&apos;s YOLO setting is on: a browse starts without asking you,
        and goes only to the domains its Expert lists.{" "}
        <Link
          className="underline underline-offset-4"
          href="/settings/browsing"
        >
          Change it in Settings → Browsing
        </Link>
        .
      </p>
    </div>
  );
}
