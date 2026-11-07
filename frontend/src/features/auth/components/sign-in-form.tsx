"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";

import { TextField } from "@/components/forms/text-field";
import { Button } from "@/components/ui/button";
import { safeNextPath } from "@/lib/navigation";

import { useSignIn } from "../hooks";
import { signInSchema, type SignInValues } from "../schemas";

import { DemoSignIn } from "./demo-sign-in";
import { FormError } from "./form-error";

export function SignInForm() {
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));
  const signIn = useSignIn();
  const form = useForm<SignInValues>({
    resolver: zodResolver(signInSchema),
    defaultValues: { email: "", password: "" },
  });
  const { errors } = form.formState;

  const goNext = () => router.replace(next);
  const onSubmit = form.handleSubmit((values) => signIn.mutate(values, { onSuccess: goNext }));

  return (
    <div className="grid gap-6">
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          autoFocus
          error={errors.email?.message}
          {...form.register("email")}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...form.register("password")}
        />
        <FormError error={signIn.error} />
        <Button type="submit" disabled={signIn.isPending}>
          {signIn.isPending ? <Loader2 className="animate-spin" /> : null}
          Sign in
        </Button>
      </form>

      <DemoSignIn onSuccess={goNext} />

      <p className="text-center text-sm text-muted-foreground">
        New to TripMind?{" "}
        <Link
          href={next === "/" ? "/sign-up" : `/sign-up?next=${encodeURIComponent(next)}`}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Create an account
        </Link>
      </p>
    </div>
  );
}
