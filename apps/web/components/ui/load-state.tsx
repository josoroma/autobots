"use client";

import Link from "next/link";
import { type ReactNode, useEffect } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { failureWords, mismatchRecord } from "@/lib/load";
import type { ResourceState } from "@/lib/use-resource";
import { cn } from "@/lib/utils";

/**
 * Records a contract mismatch in the browser console once per field, with the schema and the
 * field's path, never a value from the reply (XTYP-14, XERR-03).
 */
export function useMismatchLog(state: ResourceState<unknown>): void {
  const record = state.kind === "out_of_date" ? mismatchRecord(state) : null;
  const schema = record?.schema ?? null;
  const path = record?.path ?? null;
  useEffect(() => {
    if (path === null) return;
    console.error("This page and the local service disagree.", {
      event: "web.contract_mismatch",
      schema,
      path,
    });
  }, [schema, path]);
}

/**
 * What a screen shows instead of its content: loading, or why a read failed, in fixed words with one
 * announcement role (PRD-Development-Harness DH-06, XWEB-06). Nothing for an idle or ready read.
 * Every failure keeps `data-state="unavailable"`, which the suites read, and `data-reason` names the
 * kind. Only an unavailable read offers Retry; a signed-out one links to Sign in. `what` is a noun
 * phrase, such as "runs" or "this tool".
 */
export function LoadState({
  state,
  what,
  onRetry,
  pending = false,
  notFound,
  className,
}: {
  state: ResourceState<unknown>;
  what: string;
  onRetry?: () => void;
  /** A retry is in flight, so Retry waits. */
  pending?: boolean;
  /** The sentence for a missing item, such as "That tool isn't in the catalog." */
  notFound?: string;
  className?: string;
}) {
  useMismatchLog(state);
  if (state.kind === "idle" || state.kind === "ready") return null;
  if (state.kind === "loading") {
    return (
      <p
        role="status"
        data-state="loading"
        className={cn("text-muted-foreground text-sm", className)}
      >
        {`Loading ${what}.`}
      </p>
    );
  }
  const { words, retry } = failureWords(state, what);
  return (
    <div
      data-state="unavailable"
      data-reason={state.kind}
      className={cn(
        "border-border space-y-3 rounded-lg border p-4 text-sm",
        className,
      )}
    >
      <p role="alert">
        {state.kind === "not_found" && notFound !== undefined
          ? notFound
          : words}
      </p>
      {retry && onRetry !== undefined ? (
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          onClick={onRetry}
        >
          Retry
        </Button>
      ) : null}
      {state.kind === "signed_out" ? (
        <Link
          href="/sign-in"
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Sign in
        </Link>
      ) : null}
    </div>
  );
}

/** A screen's own empty sentence, announced like the other states. */
export function LoadEmpty({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p role="status" data-state="empty" className={cn("text-sm", className)}>
      {children}
    </p>
  );
}
