"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useSession } from "../hooks";

const dateFormat = new Intl.DateTimeFormat("en-IN", { dateStyle: "long" });

export function AccountDetails() {
  const { user } = useSession();
  if (!user) return null;

  const rows: Array<[string, string]> = [
    ["Name", user.full_name],
    ["Email", user.email],
    ["Member since", dateFormat.format(new Date(user.created_at))],
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Profile
          <Badge variant="secondary" className="capitalize">
            {user.role === "traveler" ? "Traveller" : user.role}
          </Badge>
        </CardTitle>
        <CardDescription>Your sign-in details. Trips and bookings will appear here as they are added.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-4 sm:grid-cols-[10rem_1fr]">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-sm text-muted-foreground">{label}</dt>
              <dd className="text-sm font-medium break-all">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
