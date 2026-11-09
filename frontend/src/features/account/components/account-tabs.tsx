"use client";

import { useRouter, useSearchParams } from "next/navigation";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AccountDetails } from "@/features/auth/components/account-details";

import { PriceAlertsSection, RecentSearchesSection, ReviewsSection, SavedStaysSection, SecuritySection } from "./account-sections";
import { LoyaltyCard, SavedTravellersCard } from "./account-extras";

const TABS = [
  { value: "profile", label: "Profile" },
  { value: "saved", label: "Saved stays" },
  { value: "alerts", label: "Price alerts" },
  { value: "reviews", label: "Reviews" },
  { value: "searches", label: "Recent searches" },
  { value: "security", label: "Security and privacy" },
];

/** The tab lives in the URL, so "Saved stays" in the account menu and a shared link both land on it. */
export function AccountTabs() {
  const params = useSearchParams();
  const router = useRouter();
  const tab = TABS.some((item) => item.value === params.get("tab")) ? params.get("tab")! : "profile";

  return (
    <Tabs value={tab} onValueChange={(value) => router.replace(`/account?tab=${value}`, { scroll: false })} className="grid gap-5">
      <TabsList className="h-auto w-full flex-wrap justify-start">
        {TABS.map((item) => (
          <TabsTrigger key={item.value} value={item.value} className="flex-none">
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="profile" className="grid gap-4">
        <AccountDetails />
        <LoyaltyCard />
        <SavedTravellersCard />
      </TabsContent>
      <TabsContent value="saved">
        <SavedStaysSection />
      </TabsContent>
      <TabsContent value="alerts">
        <PriceAlertsSection />
      </TabsContent>
      <TabsContent value="reviews">
        <ReviewsSection />
      </TabsContent>
      <TabsContent value="searches">
        <RecentSearchesSection />
      </TabsContent>
      <TabsContent value="security">
        <SecuritySection />
      </TabsContent>
    </Tabs>
  );
}
