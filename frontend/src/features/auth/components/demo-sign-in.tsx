"use client";

import { Loader2, UserRound, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useFeatures } from "@/features/meta/use-features";

import type { DemoRole } from "../api";
import { useDemoSignIn } from "../hooks";

import { FormError } from "./form-error";

/** One-click access to seeded demo accounts. Rendered only when the `demo_login` flag is on. */
export function DemoSignIn({ onSuccess }: { onSuccess: () => void }) {
  const { enabled } = useFeatures();
  const demo = useDemoSignIn();

  if (!enabled("demo_login")) return null;

  const signIn = (role: DemoRole) => demo.mutate(role, { onSuccess });
  const pendingRole = demo.isPending ? demo.variables : undefined;

  return (
    <div className="grid gap-3">
      <div className="flex items-center gap-3 text-xs uppercase tracking-wide text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        Demo access
        <span className="h-px flex-1 bg-border" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button type="button" variant="outline" disabled={demo.isPending} onClick={() => signIn("traveler")}>
          {pendingRole === "traveler" ? <Loader2 className="animate-spin" /> : <UserRound />}
          Traveller
        </Button>
        <Button type="button" variant="outline" disabled={demo.isPending} onClick={() => signIn("admin")}>
          {pendingRole === "admin" ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
          Admin
        </Button>
      </div>
      <FormError error={demo.error} />
    </div>
  );
}
