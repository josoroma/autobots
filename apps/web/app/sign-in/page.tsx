import { SignInForm } from "@/components/sign-in-form";
import { Card } from "@/components/ui/card";

export default function SignInPage() {
  return (
    <div className="max-w-md space-y-6">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <Card aria-labelledby="sign-in-heading" className="space-y-3">
        <h2 id="sign-in-heading" className="text-lg font-medium">
          Local account
        </h2>
        <p className="text-muted-foreground text-sm">
          Your account lives on this Mac. There is no public signup.
        </p>
        <SignInForm />
      </Card>
    </div>
  );
}
