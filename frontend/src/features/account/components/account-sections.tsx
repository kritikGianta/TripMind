"use client";

import { BellRing, BookmarkX, Download, History, KeyRound, LogOut, MessageSquareText, ShieldAlert, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { FormError } from "@/features/auth/components/form-error";
import { useSession } from "@/features/auth/hooks";
import { formatMoney } from "@/features/search/format";
import { errorMessage } from "@/lib/api/errors";

import {
  downloadMyData,
  searchLink,
  useChangePassword,
  useDeleteAccount,
  useDeleteAlert,
  useDeleteReview,
  useForgetSearch,
  useMyReviews,
  usePriceAlerts,
  useRecentSearches,
  useSavedHotels,
  useSignOutEverywhere,
  useToggleSaved,
} from "../self-service";

function Empty({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="grid justify-items-center gap-2 py-8 text-center text-muted-foreground">
      {icon}
      <p className="max-w-md">{children}</p>
    </div>
  );
}

const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

export function SavedStaysSection() {
  const { data, isPending } = useSavedHotels();
  const toggle = useToggleSaved();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Saved stays</CardTitle>
        <CardDescription>Stays you want to come back to. Saving one also helps your recommendations.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {isPending ? <Skeleton className="h-24 w-full sm:col-span-2" /> : null}
        {data && data.items.length === 0 ? (
          <div className="sm:col-span-2">
            <Empty icon={<BookmarkX className="size-8" aria-hidden />}>Nothing saved yet. Open any stay and choose Save.</Empty>
          </div>
        ) : null}
        {data?.items.map((hotel) => (
          <div key={hotel.hotel_id} className="flex items-start justify-between gap-3 rounded-sm border p-3">
            <div className="min-w-0">
              <Link href={`/stays/${hotel.hotel_id}`} className="font-medium hover:underline">
                {hotel.name}
              </Link>
              <p className="text-sm text-muted-foreground">
                {hotel.city_name}
                {hotel.star_rating ? ` · ${hotel.star_rating} star` : ""}
                {hotel.guest_rating ? ` · ${hotel.guest_rating}/10` : ""}
              </p>
              {!hotel.available ? <Badge variant="outline">No longer listed</Badge> : null}
            </div>
            <Button
              variant="ghost"
              size="sm"
              disabled={toggle.isPending}
              aria-label={`Remove ${hotel.name}`}
              onClick={() => toggle.mutate({ hotelId: hotel.hotel_id, saved: true })}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

const ALERT_STATUS: Record<string, string> = { watching: "Watching", triggered: "Price dropped", expired: "Date passed", cancelled: "Stopped" };

export function PriceAlertsSection() {
  const { data, isPending } = usePriceAlerts();
  const remove = useDeleteAlert();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Price alerts</CardTitle>
        <CardDescription>We re-check these regularly and notify you once when the price falls.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {isPending ? <Skeleton className="h-24 w-full" /> : null}
        {data && data.items.length === 0 ? (
          <Empty icon={<BellRing className="size-8" aria-hidden />}>No alerts yet. Choose Watch price on a flight search or a stay.</Empty>
        ) : null}
        {data?.items.map((alert) => (
          <div key={alert.id} className="grid gap-2 rounded-sm border p-3 sm:grid-cols-[1fr_auto] sm:items-center">
            <div className="min-w-0">
              <Link href={alert.link} className="font-medium hover:underline">
                {alert.label}
              </Link>
              <p className="text-sm text-muted-foreground">
                Was {formatMoney(alert.baseline)}
                {alert.current ? ` · now ${formatMoney(alert.current)}` : ""} · lowest {formatMoney(alert.lowest)}
                {alert.target ? ` · target ${formatMoney(alert.target)}` : ""}
              </p>
              <p className="text-xs text-muted-foreground">{alert.rule}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={alert.status === "triggered" ? "default" : "secondary"}>{ALERT_STATUS[alert.status] ?? alert.status}</Badge>
              <Button variant="ghost" size="sm" disabled={remove.isPending} aria-label={`Stop watching ${alert.label}`} onClick={() => remove.mutate(alert.id)}>
                <Trash2 />
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function RecentSearchesSection() {
  const { data, isPending } = useRecentSearches();
  const forget = useForgetSearch();
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>Recent searches</CardTitle>
          <CardDescription>Pick up where you left off. Clearing them removes them for good.</CardDescription>
        </div>
        {data?.items.length ? (
          <Button variant="outline" size="sm" disabled={forget.isPending} onClick={() => forget.mutate(null)}>
            Clear all
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="grid gap-2">
        {isPending ? <Skeleton className="h-24 w-full" /> : null}
        {data && data.items.length === 0 ? <Empty icon={<History className="size-8" aria-hidden />}>No recent searches.</Empty> : null}
        {data?.items.map((search) => (
          <div key={search.id} className="flex items-center justify-between gap-3 border-t py-2 first:border-0">
            <div className="min-w-0">
              <Link href={searchLink(search)} className="font-medium hover:underline">
                {search.label}
              </Link>
              <p className="text-xs text-muted-foreground">
                {search.vertical === "flights" ? "Flights" : "Stays"} · {search.result_count} results · {day.format(new Date(search.searched_at))}
              </p>
            </div>
            <Button variant="ghost" size="sm" disabled={forget.isPending} aria-label={`Forget ${search.label}`} onClick={() => forget.mutate(search.id)}>
              <Trash2 />
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function ReviewsSection() {
  const { data, isPending } = useMyReviews();
  const remove = useDeleteReview();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your reviews</CardTitle>
        <CardDescription>Only guests who stayed can review, so every review here is a verified stay.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {isPending ? <Skeleton className="h-24 w-full" /> : null}
        {data?.awaiting.map((item) => (
          <div key={item.item_id} className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-primary/30 bg-muted p-3">
            <p>
              How was <span className="font-medium">{item.hotel_name}</span>? You checked out on {day.format(new Date(item.checked_out_on))}.
            </p>
            <Button asChild size="sm">
              <Link href={`/bookings/${item.booking_id}?review=${item.item_id}`}>Write a review</Link>
            </Button>
          </div>
        ))}
        {data && data.written.length === 0 && data.awaiting.length === 0 ? (
          <Empty icon={<MessageSquareText className="size-8" aria-hidden />}>You can review a stay after you check out.</Empty>
        ) : null}
        {data?.written.map((review) => (
          <article key={review.id} className="grid gap-1 rounded-sm border p-3">
            <div className="flex items-center justify-between gap-2">
              <Link href={`/stays/${review.hotel_id}`} className="font-medium hover:underline">
                {review.hotel_name}
              </Link>
              <div className="flex items-center gap-2">
                {review.rating !== null ? (
                  <span className="flex items-center gap-1 text-sm">
                    <Star className="size-3.5 fill-current" aria-hidden /> {review.rating}/10
                  </span>
                ) : null}
                <Button variant="ghost" size="sm" disabled={remove.isPending} aria-label={`Delete review of ${review.hotel_name}`} onClick={() => remove.mutate(review.id)}>
                  <Trash2 />
                </Button>
              </div>
            </div>
            {review.title ? <p className="font-medium">{review.title}</p> : null}
            <p className="text-sm text-muted-foreground">{review.text}</p>
          </article>
        ))}
      </CardContent>
    </Card>
  );
}

function PasswordCard() {
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    change.mutate(
      { current_password: current, new_password: next },
      {
        onSuccess: () => {
          toast.success("Password changed. Other devices have been signed out.");
          setCurrent("");
          setNext("");
        },
      },
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4" aria-hidden /> Password
        </CardTitle>
        <CardDescription>Changing it signs out your other devices.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="current-password">Current password</Label>
            <Input id="current-password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="new-password">New password</Label>
            <Input id="new-password" type="password" autoComplete="new-password" minLength={8} value={next} onChange={(e) => setNext(e.target.value)} required />
          </div>
          <div className="grid gap-2 sm:col-span-2">
            <FormError error={change.error} />
            <Button type="submit" className="w-fit" disabled={change.isPending}>
              Change password
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export function SecuritySection() {
  const router = useRouter();
  const everywhere = useSignOutEverywhere();
  const remove = useDeleteAccount();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [exporting, setExporting] = useState(false);
  // A guest has no password anyone knows, so password, session and account-deletion controls
  // do not apply; downloading their data still does.
  const guest = useSession().user?.is_guest ?? false;

  return (
    <div className="grid gap-4">
      {guest ? null : <PasswordCard />}
      {guest ? null : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <LogOut className="size-4" aria-hidden /> Sessions
            </CardTitle>
            <CardDescription>Signs you out on every device, including this one.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2">
            {everywhere.error ? <FormError error={everywhere.error} /> : null}
            <Button variant="outline" className="w-fit" disabled={everywhere.isPending} onClick={() => everywhere.mutate(undefined, { onSuccess: () => router.replace("/sign-in") })}>
              Sign out everywhere
            </Button>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="size-4" aria-hidden /> Your data
          </CardTitle>
          <CardDescription>Everything we hold about you, as one file you can keep.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            disabled={exporting}
            onClick={() => {
              setExporting(true);
              downloadMyData()
                .catch((error) => toast.error(errorMessage(error)))
                .finally(() => setExporting(false));
            }}
          >
            <Download /> {exporting ? "Preparing…" : "Download my data"}
          </Button>
        </CardContent>
      </Card>
      {guest ? null : (
        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <ShieldAlert className="size-4" aria-hidden /> Delete account
            </CardTitle>
            <CardDescription>Removes your personal details for good. Records of past bookings are kept without your name, as the law requires.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="destructive" onClick={() => setConfirming(true)}>
              Delete my account
            </Button>
          </CardContent>
        </Card>
      )}
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete your account?</DialogTitle>
            <DialogDescription>This can&apos;t be undone. Enter your password to confirm.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="delete-password">Password</Label>
            <Input id="delete-password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <FormError error={remove.error} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirming(false)}>
              Keep my account
            </Button>
            <Button variant="destructive" disabled={!password || remove.isPending} onClick={() => remove.mutate(password, { onSuccess: () => router.replace("/") })}>
              Delete for good
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
