import type { Metadata } from "next";
import { Suspense } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ResetPasswordForm } from "@/features/auth/components/password-recovery";

export const metadata: Metadata = { title: "Set a new password" };

export default function Page() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Set a new password</CardTitle>
        <CardDescription>Choose something you have not used here before.</CardDescription>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<Skeleton className="h-40 w-full" />}>
          <ResetPasswordForm />
        </Suspense>
      </CardContent>
    </Card>
  );
}
