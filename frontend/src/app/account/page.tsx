import type { Metadata } from "next";

import { AccountDetails } from "@/features/auth/components/account-details";
import { RequireAuth } from "@/features/auth/components/require-auth";

export const metadata: Metadata = { title: "Account" };

export default function AccountPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Account</h1>
      <RequireAuth>
        <AccountDetails />
      </RequireAuth>
    </div>
  );
}
