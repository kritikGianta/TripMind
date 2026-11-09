/**
 * Product identity and navigation. Rebranding for the finale means editing this file only.
 */
export const siteConfig = {
  name: "TripMind",
  tagline: "Book a flight, a stay, or the whole trip.",
  description:
    "TripMind is a travel booking platform: book a flight or a hotel on its own, or plan both together as one connected trip.",
  disclaimer:
    "TripMind is a hackathon prototype. It is not affiliated with or endorsed by Booking Holdings or any travel provider.",
  nav: [
    { href: "/", label: "Home" },
    { href: "/flights", label: "Flights" },
    { href: "/stays", label: "Stays" },
    { href: "/explore", label: "Explore" },
    { href: "/plan", label: "Plan a trip" },
    { href: "/trips", label: "My Trips" },
    { href: "/support", label: "Support" },
    { href: "/about", label: "About" },
  ],
} as const;

export type NavItem = (typeof siteConfig.nav)[number];
