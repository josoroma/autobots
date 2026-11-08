import { SignInForm } from "@/components/sign-in-form";
import { Card } from "@/components/ui/card";

// Decision 0021: a narrow centered column, a serif title and one quiet card holding the form.
export default function SignInPage() {
  return (
    <div className="mx-auto w-full max-w-sm space-y-6 md:pt-16">
      <h1 className="text-center text-[32px] leading-tight">Sign in</h1>
      <Card
        aria-labelledby="sign-in-heading"
        className="border-input space-y-5 rounded-2xl p-6 shadow-lg dark:shadow-black/60"
      >
        <div className="space-y-1">
          <h2 id="sign-in-heading" className="text-base font-medium">
            Local account
          </h2>
          <p className="text-muted-foreground text-sm">
            Your account lives on this Mac. There is no public signup.
          </p>
        </div>
        <SignInForm />
      </Card>
    </div>
  );
}
