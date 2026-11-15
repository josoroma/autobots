"use client";

import { CircleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { failureOf, signIn } from "@/lib/api/browser";
import {
  SIGN_IN_FAILURE_TEXT,
  signInFailure,
  type SignInFailure,
} from "@/lib/sign-in-failure";

// The credential sentence is only for the session route's 401. A refusal or an outage, including
// no reply at all, has its own sentence (WSHL-07).
export function SignInForm() {
  const router = useRouter();
  const [failed, setFailed] = useState<SignInFailure | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPending(true);
    setFailed(null);
    const form = new FormData(event.currentTarget);
    const field = (name: string) => {
      const value = form.get(name);
      return typeof value === "string" ? value : "";
    };
    let failure: SignInFailure | null = null;
    try {
      await signIn({ email: field("email"), password: field("password") });
    } catch (error) {
      failure = signInFailure(failureOf(error).status);
    }
    setPending(false);
    if (failure === null) {
      router.push("/");
      router.refresh();
    } else {
      setFailed(failure);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-4">
      <Field id="email" label="Email">
        {(control) => (
          <Input
            {...control}
            name="email"
            type="email"
            autoComplete="username"
            required
          />
        )}
      </Field>
      <Field id="password" label="Password">
        {(control) => (
          <Input
            {...control}
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        )}
      </Field>
      {failed === null ? null : (
        <p
          role="alert"
          data-sign-in-failure={failed}
          className="flex items-start gap-2 text-sm font-medium"
        >
          <CircleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          {SIGN_IN_FAILURE_TEXT[failed]}
        </p>
      )}
      <Button type="submit" size="lg" disabled={pending} className="w-full">
        {pending ? "Signing in" : "Sign in"}
      </Button>
    </form>
  );
}
