import type { Metadata } from "next";
import { Suspense } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SignInForm } from "@/features/auth/components/sign-in-form";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Welcome back</CardTitle>
        <CardDescription>Sign in to manage your trips and bookings.</CardDescription>
      </CardHeader>
      <CardContent>
        {/* The form reads `?next=` from the URL, which needs a Suspense boundary. */}
        <Suspense fallback={<Skeleton className="h-64 w-full" />}>
          <SignInForm />
        </Suspense>
      </CardContent>
    </Card>
  );
}
