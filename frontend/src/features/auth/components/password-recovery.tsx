"use client";

import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useForgotPassword, useResetPassword } from "@/features/account/self-service";

import { FormError } from "./form-error";

export function ForgotPasswordForm() {
  const forgot = useForgotPassword();

  // Read from the form itself, so anything typed before the page finished loading still counts.
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    forgot.mutate(String(new FormData(event.currentTarget).get("email")).trim());
  }

  if (forgot.data) {
    return (
      <div className="grid gap-3">
        <Alert>
          <CheckCircle2 />
          <AlertDescription>{forgot.data.message}</AlertDescription>
        </Alert>
        {/* Only returned outside production, where no email is sent, so the flow can be demonstrated. */}
        {forgot.data.dev_reset_token ? (
          <Button asChild>
            <Link href={`/reset-password?token=${encodeURIComponent(forgot.data.dev_reset_token)}`}>Demo: reset it now</Link>
          </Button>
        ) : null}
        <Button asChild variant="outline">
          <Link href="/sign-in">Back to sign in</Link>
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="grid gap-1.5">
        <Label htmlFor="forgot-email">Email</Label>
        <Input id="forgot-email" name="email" type="email" autoComplete="email" required />
      </div>
      <FormError error={forgot.error} />
      <Button type="submit" disabled={forgot.isPending}>
        {forgot.isPending ? "Sending…" : "Send reset link"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Remembered it?{" "}
        <Link href="/sign-in" className="font-medium text-foreground underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </form>
  );
}

export function ResetPasswordForm() {
  const params = useSearchParams();
  const router = useRouter();
  const reset = useResetPassword();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    reset.mutate({ token, new_password: password }, { onSuccess: () => router.replace("/sign-in") });
  }

  if (!token) {
    return (
      <div className="grid gap-3">
        <Alert variant="destructive">
          <AlertDescription>This reset link isn&apos;t complete. Ask for a new one.</AlertDescription>
        </Alert>
        <Button asChild variant="outline">
          <Link href="/forgot-password">Get a new link</Link>
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="grid gap-1.5">
        <Label htmlFor="reset-password">New password</Label>
        <Input id="reset-password" type="password" autoComplete="new-password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />
        <p className="text-xs text-muted-foreground">At least 8 characters.</p>
      </div>
      <FormError error={reset.error} />
      <Button type="submit" disabled={reset.isPending}>
        {reset.isPending ? "Saving…" : "Set new password"}
      </Button>
    </form>
  );
}
