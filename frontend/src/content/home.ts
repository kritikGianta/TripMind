/**
 * Words and media on the home page. The layout lives in features/home; change the copy here.
 *
 * Every claim must match what the product does. Numbers come from the backend: the 15-minute hold
 * from config/rules.yaml, Delhi-Goa distance and flying time from the dataset generator's formula.
 */

export type MediaSlotInfo = {
  kind: "image" | "video";
  /** Where it appears, for the person choosing the file. */
  section: string;
  /** What to shoot or find. */
  brief: string;
  /** Size to aim for. */
  size: string;
  alt: string;
  /** Painted while the file is missing. */
  tone: string;
};

const sky = (a: string, b: string, c: string) => `linear-gradient(170deg, ${a} 0%, ${b} 55%, ${c} 100%)`;

/**
 * Drop a file named `<slot>.<ext>` into frontend/public/home/ and it replaces the placeholder.
 * Images: jpg, jpeg, png, webp, avif. Video: mp4, webm. For a video, an image with the same name
 * becomes its poster.
 */
export const homeMedia = {
  "hero-film": {
    kind: "video",
    section: "Hero, full screen behind the TRIPMIND wordmark",
    brief: "10-20 s silent loop. One clear subject in the upper two thirds: aircraft wing over clouds or a traveller on a ridge. Blue or dusk tones so white text reads.",
    size: "1920x1080 or larger, under 15 MB",
    alt: "A traveller's view from high above the clouds",
    tone: sky("#7b93ad", "#3f5d7c", "#14263d"),
  },
  "brand-film": {
    kind: "video",
    section: "Popup opened by 'Watch the film' (hero and footer)",
    brief: "30-90 s with sound: a TripMind demo or travel montage. Optional; the popup shows a placeholder until it exists.",
    size: "1920x1080, under 80 MB",
    alt: "The TripMind film",
    tone: sky("#20304a", "#101a2c", "#05080f"),
  },
  "ridge-landscape": {
    kind: "image",
    section: "'Works with the AI off'; the top edge is cut into a jagged ridge by code",
    brief: "Mountains or rock filling the whole frame, no sky needed. Himalaya, Ladakh or Spiti, warm rock against snow.",
    size: "2400x1400",
    alt: "A snow and rock mountain range",
    tone: sky("#c9ced6", "#8c6f5e", "#5d4436"),
  },
  "way-flights": {
    kind: "image",
    section: "'Ways to travel' strip: Book a flight",
    brief: "Portrait, subject centred because the strip crops the sides: aircraft on the tarmac at golden hour or a window seat view.",
    size: "1200x1500",
    alt: "An aircraft at golden hour",
    tone: sky("#9bb7d4", "#5f86ad", "#2f4a68"),
  },
  "way-stays": {
    kind: "image",
    section: "'Ways to travel' strip: Book a stay",
    brief: "Portrait, subject centred: hotel room with a view, or a pool at dusk. Warm light.",
    size: "1200x1500",
    alt: "A hotel room with a view",
    tone: sky("#e3c9a8", "#c08a5e", "#70472c"),
  },
  "way-plan": {
    kind: "image",
    section: "'Ways to travel' strip: Plan the whole trip",
    brief: "Portrait, subject centred: road winding through hills, or a traveller with a map.",
    size: "1200x1500",
    alt: "A road winding through hills",
    tone: sky("#b5cdb9", "#6d9a80", "#2c5145"),
  },
  "way-together": {
    kind: "image",
    section: "'Ways to travel' strip: Plan it together",
    brief: "Portrait, subject centred: friends or family looking at one phone, or walking together on a trip.",
    size: "1200x1500",
    alt: "Friends planning a trip together",
    tone: sky("#e6b7a9", "#c5786b", "#6d3440"),
  },
  "way-describe": {
    kind: "image",
    section: "'Ways to travel' strip: Just describe it",
    brief: "Portrait, subject centred: a hand holding a phone with a scenic blurred background.",
    size: "1200x1500",
    alt: "A phone held up against a scenic view",
    tone: sky("#c3bfe0", "#7f7ab8", "#37346b"),
  },
  "dest-opening": {
    kind: "image",
    section: "'Where it takes you' opening panel, expands to full screen",
    brief: "Wide, calm aerial of India: Western Ghats, or a coast seen from a plane. Soft colour so white text reads.",
    size: "2400x1350",
    alt: "A wide aerial view of a coastline",
    tone: sky("#cfd9dd", "#a6b8a8", "#6c8569"),
  },
  "dest-backdrop": {
    kind: "image",
    section: "'Where it takes you' backdrop behind the moving cards",
    brief: "Top-down drone texture, no horizon: waves on sand, backwaters, or tea-garden rows. Rich colour, little detail.",
    size: "2400x1350",
    alt: "A top-down view of waves meeting the shore",
    tone: sky("#5ec3c9", "#2d97a6", "#0f5e73"),
  },
  "dest-goa": {
    kind: "image",
    section: "Destination card: Goa",
    brief: "Goa beach at golden hour, or a Portuguese-era church. Landscape.",
    size: "1400x1050",
    alt: "A beach in Goa at golden hour",
    tone: sky("#f2c48d", "#e08a5f", "#7b3f3a"),
  },
  "dest-jaipur": {
    kind: "image",
    section: "Destination card: Jaipur",
    brief: "Hawa Mahal or Amber Fort, warm pink sandstone. Landscape.",
    size: "1400x1050",
    alt: "A palace in Jaipur",
    tone: sky("#f0b8a2", "#cf7760", "#71352c"),
  },
  "dest-kochi": {
    kind: "image",
    section: "Destination card: Kochi",
    brief: "Chinese fishing nets at sunset, or Kerala backwaters. Landscape.",
    size: "1400x1050",
    alt: "Fishing nets in Kochi at sunset",
    tone: sky("#a7cfb6", "#58967f", "#1f4f4a"),
  },
  "dest-udaipur": {
    kind: "image",
    section: "Destination card: Udaipur",
    brief: "City Palace over Lake Pichola at dusk. Landscape.",
    size: "1400x1050",
    alt: "A palace over a lake in Udaipur",
    tone: sky("#c9c6e6", "#8d8dc4", "#3f4379"),
  },
  "dest-srinagar": {
    kind: "image",
    section: "Destination card: Srinagar",
    brief: "Shikara on Dal Lake with mountains behind. Landscape.",
    size: "1400x1050",
    alt: "A shikara on Dal Lake in Srinagar",
    tone: sky("#b9d4e6", "#6fa3c4", "#2b5671"),
  },
  "proof-landscape": {
    kind: "image",
    section: "'Seven models. None required.' full screen, white text on top",
    brief: "Bright, spacious landscape with one small human figure near the centre: dunes, salt flats (Rann of Kutch) or snow. Keep the centre uncluttered.",
    size: "2400x1500",
    alt: "A single traveller in a wide landscape",
    tone: sky("#c6d3ea", "#8fa9d4", "#5372a8"),
  },
  "route-opening": {
    kind: "image",
    section: "Giant DEL — GOI route code; the photo fades into white as you scroll",
    brief: "High-key, bright photo: clouds from a plane window, or the Arabian Sea from the air. Light colours so the fade to white looks natural.",
    size: "2400x1500",
    alt: "Clouds seen from a plane window",
    tone: sky("#d5e3f2", "#a9c4e0", "#7fa3cb"),
  },
  "route-origin": {
    kind: "image",
    section: "Dark journey map, top: where the route starts",
    brief: "Satellite or night-lights view of Delhi or north India on a near-black background. Edges fade into black in code. Optional.",
    size: "1400x900",
    alt: "North India from space at night",
    tone: "radial-gradient(60% 70% at 50% 30%, #3a4150 0%, #161a22 60%, #090b10 100%)",
  },
  "route-destination": {
    kind: "image",
    section: "Dark journey map, bottom: where the route ends",
    brief: "Satellite view of the Goa or Konkan coast on a near-black background. Edges fade into black in code. Optional.",
    size: "1400x900",
    alt: "The Goa coast from space",
    tone: "radial-gradient(60% 70% at 50% 70%, #3a4a50 0%, #151b20 60%, #090b10 100%)",
  },
  "cta-landscape": {
    kind: "image",
    section: "Final 'Start planning' full screen, also the footer film tile",
    brief: "Travellers walking away from camera in a big landscape, with calm sky or snow in the centre for the text.",
    size: "2400x1500",
    alt: "Travellers walking through a wide landscape",
    tone: sky("#8fb3d1", "#c6d8e6", "#e7eef3"),
  },
} satisfies Record<string, MediaSlotInfo>;

export type MediaSlot = keyof typeof homeMedia;

export const homeCopy = {
  hero: { wordmark: "TripMind", film: "Watch the film" },
  search: {
    label: "Start here",
    heading: "Where to next?",
    note: "Book one thing on its own, or describe the whole trip in a sentence.",
  },
  statement: {
    label: "One trip, one place",
    text: "A flight here, a hotel there, and nobody checking that they fit together. TripMind plans, books and looks after the whole journey.",
  },
  promise: {
    label: "Works with the AI off",
    text: "Search, prices, holds, payment and refunds all run on plain rules and real inventory. AI fills in the form, explains and ranks. You choose. If every AI provider went down tomorrow, you could still book your trip.",
  },
  ways: {
    heading: "Ways to travel",
    items: [
      {
        slot: "way-flights",
        title: ["Book", "a flight"],
        tag: "On its own",
        meta: "Direct or one stop",
        text: "Compare fares, stops and journey times, one-way or return, with every price itemised and a label saying if it is below, near or above typical.",
        cta: "Search flights",
        href: "/flights",
      },
      {
        slot: "way-stays",
        title: ["Book", "a stay"],
        tag: "On its own",
        meta: "Whole-stay price",
        text: "Find hotels by city, dates and guests. The price for the whole stay is shown upfront, with similar stays on every hotel page.",
        cta: "Search stays",
        href: "/stays",
      },
      {
        slot: "way-plan",
        title: ["Plan", "the whole trip"],
        tag: "Connected",
        meta: "One checkout",
        text: "Give dates and a destination. Compare complete flight-and-stay trips, ranked with reasons, and book them together.",
        cta: "Plan a trip",
        href: "/plan",
      },
      {
        slot: "way-together",
        title: ["Plan it", "together"],
        tag: "Groups",
        meta: "Love, OK or No",
        text: "Share a plan by link. Everyone votes and sets a budget, the consensus is shown openly, and the organiser decides and books.",
        cta: "Start a plan",
        href: "/plan",
      },
      {
        slot: "way-describe",
        title: ["Just", "describe it"],
        tag: "AI optional",
        meta: "A sentence is enough",
        text: "Type what you want in your own words. It becomes a filled search form that you check, change and book yourself.",
        cta: "Try it",
        href: "#search",
      },
    ],
  },
  confidence: {
    label: "Journey Confidence Report",
    text: "Two good prices can still make a bad trip. So every planned trip comes with a plain-language report on how the flight and the stay fit together, and what to watch for.",
    checks: [
      { name: "Connections", text: "Enough time to change planes, and a warning if bags may need re-checking." },
      { name: "Arrival and check-in", text: "How long you would wait after landing, before the 14:00 check-in." },
      { name: "Check-out and return", text: "When to leave the hotel, and the gap before your return flight." },
    ],
  },
  destinations: {
    heading: "Where it takes you",
    label: "From anywhere to everywhere",
    text: "A small part of what you can search. Prices are live from our demo dataset: return flights and three nights for two from Delhi, before any taxes the data lacks.",
    origin: { code: "DEL", label: "Delhi" },
    nights: 3,
    adults: 2,
    items: [
      { slot: "dest-goa", city: "Goa", text: "Long beaches, Portuguese-era churches and slow lunches.", coords: "15° 29′ N, 73° 50′ E" },
      { slot: "dest-jaipur", city: "Jaipur", text: "Forts, bazaars and palaces in pink sandstone.", coords: "26° 55′ N, 75° 47′ E" },
      { slot: "dest-kochi", city: "Kochi", text: "Fishing nets, spice markets and the road to the backwaters.", coords: "9° 56′ N, 76° 16′ E" },
      { slot: "dest-udaipur", city: "Udaipur", text: "White palaces reflected in quiet lakes.", coords: "24° 35′ N, 73° 43′ E" },
      { slot: "dest-srinagar", city: "Srinagar", text: "Houseboats on Dal Lake with mountains behind.", coords: "34° 05′ N, 74° 48′ E" },
    ],
  },
  proof: {
    label: "How it is built",
    text: "Seven models. None of them required.",
    note: "Hotel ranking, fare labels, review reading, request filing and more. Each has plain rules underneath, so nothing stops when a model does.",
    cta: "See how we measured",
  },
  route: {
    code: ["DEL", "GOI"],
    from: { coords: "28° 33′ 22″ N, 77° 06′ 01″ E", place: "Delhi" },
    to: { coords: "15° 22′ 51″ N, 73° 49′ 53″ E", place: "Goa, Dabolim" },
    heading: "Booked is not the end",
    text: "Most sites stop at the confirmation email. When a flight is cancelled or delayed, or a room falls through, TripMind finds the affected booking, offers you options and replaces only what you approve.",
    start: { label: "Starting point", place: "Delhi" },
    end: { label: "Landing", place: "Goa" },
    example: "Example journey",
    stats: [
      { label: "Flying time", value: "2h 35m" },
      { label: "Distance", value: "1,503 km" },
      { label: "Price held for", value: "15 min" },
    ],
    stages: [
      { name: "Held", text: "Your price is held for 15 minutes while you pay.", alert: false },
      { name: "Booked", text: "Flight and stay on one itinerary, with an itemised price and an invoice.", alert: false },
      { name: "Flight cancelled", text: "TripMind finds the affected booking and alerts you in the app.", alert: true },
      { name: "Recovered", text: "You choose the option. Only the affected item is replaced.", alert: false },
    ],
  },
  cta: { heading: "Start planning your next trip", action: "Plan a trip" },
  how: {
    heading: "How it works",
    tab: "How it works",
    steps: [
      { name: "1. Search or describe", text: "Use the forms, or type a sentence and check the form AI fills in. Don't include personal details." },
      { name: "2. Compare", text: "See fare labels, whole-stay prices and complete trips ranked with reasons. Unknown fees are marked, not hidden." },
      { name: "3. Hold and pay", text: "Your price is held for 15 minutes. Paying twice by accident is blocked, and every price is itemised." },
      { name: "4. Travel, and recover", text: "If something changes you get an alert and options. Approve one, and only the affected item is replaced." },
    ],
  },
  menu: [
    {
      title: "Book",
      links: [
        { label: "Flights", href: "/flights" },
        { label: "Stays", href: "/stays" },
        { label: "Plan a trip", href: "/plan" },
      ],
    },
    {
      title: "Your travel",
      links: [
        { label: "My Trips", href: "/trips" },
        { label: "Account", href: "/account" },
      ],
    },
    {
      title: "TripMind",
      links: [{ label: "About", href: "/about" }],
    },
  ],
} as const;
