"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";

export function SignInForm() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPending(true);
    setFailed(false);
    const form = new FormData(event.currentTarget);
    const reply = await csrfFetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
      }),
    }).catch(() => null);
    setPending(false);
    if (reply?.ok === true) {
      router.push("/");
      router.refresh();
    } else {
      setFailed(true);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-3">
      <div className="space-y-1">
        <label htmlFor="email" className="text-sm font-medium">
          Email
        </label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          required
        />
      </div>
      <div className="space-y-1">
        <label htmlFor="password" className="text-sm font-medium">
          Password
        </label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
      </div>
      {failed ? (
        <p role="alert" className="text-sm font-medium">
          That email and password did not work.
        </p>
      ) : null}
      <Button type="submit" disabled={pending}>
        {pending ? "Signing in" : "Sign in"}
      </Button>
    </form>
  );
}
