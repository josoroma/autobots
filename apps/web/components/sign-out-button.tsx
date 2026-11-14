"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { csrfFetch } from "@/lib/csrf-fetch";

// A sign-out that is refused or gets no reply says so, rather than leaving the person signed in
// with nothing shown (WSHL-07).
export function SignOutButton({ className }: { className?: string }) {
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  async function signOut(): Promise<void> {
    setFailed(false);
    const reply = await csrfFetch("/api/session", { method: "DELETE" }).catch(
      () => null,
    );
    if (reply?.ok === true) {
      router.refresh();
    } else {
      setFailed(true);
    }
  }
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className={className}
        onClick={() => void signOut()}
      >
        Sign out
      </Button>
      {failed ? (
        <p role="alert" data-message="sign-out" className="px-1 pt-1 text-sm">
          Signing out did not finish. Try again.
        </p>
      ) : null}
    </>
  );
}
