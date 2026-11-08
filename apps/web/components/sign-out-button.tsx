"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { csrfFetch } from "@/lib/csrf-fetch";

export function SignOutButton({ className }: { className?: string }) {
  const router = useRouter();
  async function signOut(): Promise<void> {
    await csrfFetch("/api/session", { method: "DELETE" }).catch(() => null);
    router.refresh();
  }
  return (
    <Button
      variant="outline"
      size="sm"
      className={className}
      onClick={() => void signOut()}
    >
      Sign out
    </Button>
  );
}
