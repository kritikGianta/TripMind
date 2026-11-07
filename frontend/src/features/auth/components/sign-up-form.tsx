"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm, type Path } from "react-hook-form";

import { TextField } from "@/components/forms/text-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useFeatures } from "@/features/meta/use-features";
import { ApiError } from "@/lib/api/errors";
import { safeNextPath } from "@/lib/navigation";

import { useSignUp } from "../hooks";
import { signUpSchema, type SignUpValues } from "../schemas";

import { FormError } from "./form-error";

const FIELDS: ReadonlyArray<Path<SignUpValues>> = ["full_name", "email", "password"];

export function SignUpForm() {
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));
  const { enabled, isLoading } = useFeatures();
  const signUp = useSignUp();
  const form = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { full_name: "", email: "", password: "" },
  });
  const { errors } = form.formState;

  const onSubmit = form.handleSubmit((values) =>
    signUp.mutate(values, {
      onSuccess: () => router.replace(next),
      onError: (error) => {
        // Server-side validation lands on the matching field; anything else is a form-level error.
        if (!(error instanceof ApiError)) return;
        if (error.code === "EMAIL_TAKEN") {
          form.setError("email", { message: "An account with this email already exists." });
        }
        for (const fieldError of error.fieldErrors) {
          const field = FIELDS.find((name) => name === fieldError.field);
          if (field) form.setError(field, { message: fieldError.message });
        }
      },
    }),
  );

  const fieldLevel =
    signUp.error instanceof ApiError &&
    (signUp.error.code === "EMAIL_TAKEN" || signUp.error.code === "VALIDATION_FAILED");

  if (!isLoading && !enabled("registration")) {
    return (
      <Alert>
        <AlertDescription>New sign-ups are currently closed.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="grid gap-6">
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        <TextField
          label="Full name"
          autoComplete="name"
          autoFocus
          error={errors.full_name?.message}
          {...form.register("full_name")}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...form.register("email")}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 8 characters. A short phrase is easier to remember."
          error={errors.password?.message}
          {...form.register("password")}
        />
        {fieldLevel ? null : <FormError error={signUp.error} />}
        <Button type="submit" disabled={signUp.isPending}>
          {signUp.isPending ? <Loader2 className="animate-spin" /> : null}
          Create account
        </Button>
      </form>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link
          href={next === "/" ? "/sign-in" : `/sign-in?next=${encodeURIComponent(next)}`}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
