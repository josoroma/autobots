"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { csrfFetch } from "@/lib/csrf-fetch";

export function SignOutButton() {
  const router = useRouter();
  async function signOut(): Promise<void> {
    await csrfFetch("/api/session", { method: "DELETE" }).catch(() => null);
    router.refresh();
  }
  return (
    <Button variant="secondary" onClick={() => void signOut()}>
      Sign out
    </Button>
  );
}
