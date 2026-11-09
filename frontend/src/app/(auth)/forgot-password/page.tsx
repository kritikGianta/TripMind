import type { Metadata } from "next";
import { Suspense } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ForgotPasswordForm } from "@/features/auth/components/password-recovery";

export const metadata: Metadata = { title: "Forgot your password?" };

export default function Page() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Forgot your password?</CardTitle>
        <CardDescription>Enter your email and we will send a link to set a new one.</CardDescription>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<Skeleton className="h-40 w-full" />}>
          <ForgotPasswordForm />
        </Suspense>
      </CardContent>
    </Card>
  );
}
