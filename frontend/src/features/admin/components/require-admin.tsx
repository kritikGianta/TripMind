"use client";

import { ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { useSession } from "@/features/auth/hooks";

/** Renders admin pages for admins only. The API enforces the same rule on every request. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <AdminOnly>{children}</AdminOnly>
    </RequireAuth>
  );
}

function AdminOnly({ children }: { children: ReactNode }) {
  const { user } = useSession();
  if (user?.role !== "admin") {
    return (
      <Alert>
        <ShieldAlert />
        <AlertDescription>This page is for administrators. Use Demo access → Admin on the sign-in page.</AlertDescription>
      </Alert>
    );
  }
  return <>{children}</>;
}
