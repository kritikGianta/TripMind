/**
 * Words and media on the home page. The layout lives in features/home; change the copy here.
 *
 * Every claim must match what the product does. Numbers come from the official data: the Bengaluru-Tokyo flying time from the official flight AV 520.
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
    alt: "Snow-capped peaks catching the last light, with clouds drifting past",
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
    section: "'No AI, just rules you can check', rising up the page in front of a hazy far range",
    brief: "A mountain cut out along its own outline, transparent above it. Stok Kangri, Ladakh: public domain, by Maverick34 on Wikimedia Commons.",
    size: "2400x872, with transparency",
    alt: "Stok Kangri, a snow-streaked peak in Ladakh",
    tone: sky("#c9ced6", "#8c6f5e", "#5d4436"),
  },
  "way-flights": {
    kind: "image",
    section: "'Ways to travel' strip: Book a flight",
    brief: "Portrait, subject centred because the strip crops the sides: aircraft on the tarmac at golden hour or a window seat view.",
    size: "1200x1500",
    alt: "An aircraft wing above the clouds at sunset, seen from a window seat",
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
  "dest-tokyo": {
    kind: "image",
    section: "Destination card: Tokyo",
    brief: "Photo from the official data pack (Wikimedia Commons, credited on the page).",
    size: "1280x960",
    alt: "teamLab Planets in Tokyo",
    tone: sky("#c9c6e6", "#8d8dc4", "#3f4379"),
  },
  "dest-kyoto": {
    kind: "image",
    section: "Destination card: Kyoto",
    brief: "Photo from the official data pack (Wikimedia Commons, credited on the page).",
    size: "1280x960",
    alt: "Kiyomizu-dera temple in Kyoto",
    tone: sky("#f0b8a2", "#cf7760", "#71352c"),
  },
  "dest-osaka": {
    kind: "image",
    section: "Destination card: Osaka",
    brief: "Photo from the official data pack (Wikimedia Commons, credited on the page).",
    size: "1280x960",
    alt: "The lights of Dotonbori in Osaka",
    tone: sky("#f2c48d", "#e08a5f", "#7b3f3a"),
  },
  "dest-dubai": {
    kind: "image",
    section: "Destination card: Dubai",
    brief: "Photo from the official data pack (Wikimedia Commons, credited on the page).",
    size: "1280x960",
    alt: "The Burj Khalifa in Dubai",
    tone: sky("#b9d4e6", "#6fa3c4", "#2b5671"),
  },
  "dest-abudhabi": {
    kind: "image",
    section: "Destination card: Abu Dhabi",
    brief: "Photo from the official data pack (Wikimedia Commons, credited on the page).",
    size: "1280x960",
    alt: "Sheikh Zayed Grand Mosque in Abu Dhabi",
    tone: sky("#a7cfb6", "#58967f", "#1f4f4a"),
  },
  "proof-landscape": {
    kind: "image",
    section: "'No AI. Every rule checked.' full screen, white text on top",
    brief: "Bright, spacious landscape with one small human figure near the centre: dunes, salt flats (Rann of Kutch) or snow. Keep the centre uncluttered.",
    size: "2400x1500",
    alt: "A single traveller in a wide landscape",
    tone: sky("#c6d3ea", "#8fa9d4", "#5372a8"),
  },
  "route-opening": {
    kind: "image",
    section: "Giant BLR — NRT route code; the photo fades into white as you scroll",
    brief: "High-key, bright photo: clouds from a plane window, or the Arabian Sea from the air. Light colours so the fade to white looks natural.",
    size: "2400x1500",
    alt: "White clouds seen from the air",
    tone: sky("#d5e3f2", "#a9c4e0", "#7fa3cb"),
  },
  "route-origin": {
    kind: "image",
    section: "Dark journey map, top: where the route starts",
    brief: "Satellite or night-lights view of south India on a near-black background. Edges fade into black in code. Optional.",
    size: "1400x900",
    alt: "The lights of India at night, seen from space",
    tone: "radial-gradient(60% 70% at 50% 30%, #3a4150 0%, #161a22 60%, #090b10 100%)",
  },
  "route-destination": {
    kind: "image",
    section: "Dark journey map, bottom: where the route ends",
    brief: "Satellite view of Japan at night on a near-black background. Edges fade into black in code. Optional.",
    size: "1400x900",
    alt: "City lights seen from orbit",
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
    note: "Book a flight or a stay on its own, plan a trip, or let TripMind build the whole holiday.",
  },
  statement: {
    label: "One trip, one place",
    text: "A flight here, a hotel there, and nobody checking that they fit together. TripMind builds the whole holiday, checks every part against the rules, and keeps it right when you change something.",
  },
  promise: {
    label: "No AI, just rules you can check",
    text: "Every package is built and checked by plain rules: the flight lands on your start date, the hotel has rooms every night, the airport transfer runs when you land, and attractions are open when you visit. If a change breaks a rule, TripMind says which one.",
  },
  ways: {
    heading: "Ways to travel",
    items: [
      {
        slot: "way-flights",
        title: ["Book", "a flight"],
        tag: "On its own",
        meta: "Direct or one stop",
        text: "From Bengaluru, Delhi, Mumbai or Chennai to Japan, the UAE, Thailand, Singapore, Bali, France or the UK. Every price is itemised, and only flights with free seats are shown.",
        cta: "Search flights",
        href: "/flights",
      },
      {
        slot: "way-stays",
        title: ["Book", "a stay"],
        tag: "On its own",
        meta: "Whole-stay price",
        text: "Hotels by city, dates and guests. Only rooms free on every night of your stay are offered, and the price for the whole stay is shown upfront.",
        cta: "Search stays",
        href: "/stays",
      },
      {
        slot: "way-plan",
        title: ["Plan", "a trip"],
        tag: "Flight + stay",
        meta: "Ranked with reasons",
        text: "Pick a city and dates. TripMind combines flights both ways with a hotel, checks they fit, and ranks complete trips by price, time, stay and convenience.",
        cta: "Plan a trip",
        href: "/plan",
      },
      {
        slot: "way-describe",
        title: ["Book", "my holiday"],
        tag: "Full package",
        meta: "Cities chosen for you",
        text: "Say where from, which country, when, who and your budget, or just type it in a sentence. TripMind picks the cities and builds flights, hotels, transfers and attractions: cheapest, fastest or best rated.",
        cta: "Build my holiday",
        href: "/plan?mode=holiday",
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
    ],
  },
  confidence: {
    label: "Every rule, checked",
    text: "Two good prices can still make a bad holiday. Every package is checked from the first flight to the last transfer, and every change you make is checked again before it is saved.",
    checks: [
      { name: "Arrival", text: "The flight lands on your start date, and the airport pickup is at least an hour after landing, inside its service hours." },
      { name: "Hotels", text: "One hotel per city, rooms that fit your family, and enough rooms free on every night." },
      { name: "Days out", text: "Attractions in the city you are in, open on that day, with no two visits at once." },
    ],
  },
  destinations: {
    heading: "Where it takes you",
    label: "Seven countries, eighteen cities",
    text: "A few of the places you can go. Prices are live: return flights and three nights for two from Bengaluru. Photos: Martin Falbisoner (Kyoto, CC BY-SA 4.0), Joli Rumi (Osaka, CC BY-SA 4.0), Syced (Tokyo, CC0), Laika ac (Dubai, CC BY-SA 2.0), Guilhem Vellut (Abu Dhabi, CC BY 2.0), via Wikimedia Commons.",
    origin: { code: "BLR", label: "Bengaluru" },
    nights: 3,
    adults: 2,
    items: [
      { slot: "dest-tokyo", city: "Tokyo", text: "Neon, temples and the best train system in the world.", coords: "35° 41′ N, 139° 41′ E" },
      { slot: "dest-kyoto", city: "Kyoto", text: "Wooden temples, quiet gardens and old tea streets.", coords: "35° 00′ N, 135° 46′ E" },
      { slot: "dest-osaka", city: "Osaka", text: "Street food, bright canals and a castle in the middle.", coords: "34° 41′ N, 135° 30′ E" },
      { slot: "dest-dubai", city: "Dubai", text: "The tallest tower, desert dunes and long beaches.", coords: "25° 12′ N, 55° 16′ E" },
      { slot: "dest-abudhabi", city: "Abu Dhabi", text: "A white marble mosque, museums and a calm corniche.", coords: "24° 27′ N, 54° 22′ E" },
    ],
  },
  proof: {
    label: "How it is built",
    text: "No AI. Every rule checked.",
    note: "Packages, prices and changes run on plain rules you can read, and every booking takes its seats and rooms in one safe step, so the last room is never sold twice.",
    cta: "See how it works",
  },
  route: {
    code: ["BLR", "NRT"],
    from: { coords: "13° 11′ 55″ N, 77° 42′ 24″ E", place: "Bengaluru" },
    to: { coords: "35° 45′ 55″ N, 140° 23′ 08″ E", place: "Tokyo, Narita" },
    heading: "Booked is not the end",
    text: "Your 10-digit reservation number opens your trip any time. And if a flight is cancelled or delayed, or a room falls through, TripMind finds the affected booking, offers you options and replaces only what you approve.",
    start: { label: "Starting point", place: "Bengaluru" },
    end: { label: "Landing", place: "Tokyo" },
    example: "Example journey",
    stats: [
      { label: "Flying time", value: "7h 10m" },
      { label: "Distance", value: "about 6,700 km" },
      { label: "Reservation number", value: "10 digits" },
    ],
    stages: [
      { name: "Built", text: "Flights, hotels, transfers and attractions that pass every rule, within your budget.", alert: false },
      { name: "Confirmed", text: "Seats and rooms are reserved at once, and you get a 10-digit reservation number.", alert: false },
      { name: "Flight cancelled", text: "TripMind finds the affected booking and alerts you in the app.", alert: true },
      { name: "Recovered", text: "You choose the option. Only the affected item is replaced.", alert: false },
    ],
  },
  cta: { heading: "Start planning your next holiday", action: "Plan a trip" },
  how: {
    heading: "How it works",
    tab: "How it works",
    steps: [
      { name: "1. Tell us the trip", text: "Use the form, or type a sentence such as \"2 adults and a 6 year old from Bengaluru to Japan on 10 April for 6 nights under 3.5 lakh\"." },
      { name: "2. Compare", text: "See the cheapest, fastest and best-rated packages, each with a day-by-day plan and the total against your budget." },
      { name: "3. Change and confirm", text: "Swap a hotel or flight, add or remove attractions; every change is checked. Confirm to get a 10-digit reservation number." },
      { name: "4. Travel, and recover", text: "Everything is in My Trips. If something changes you get an alert and options, and only the affected item is replaced." },
    ],
  },
  menu: [
    {
      title: "Book",
      links: [
        { label: "Flights", href: "/flights" },
        { label: "Stays", href: "/stays" },
        { label: "Plan a trip", href: "/plan" },
        { label: "Book my holiday", href: "/plan?mode=holiday" },
      ],
    },
    {
      title: "Your travel",
      links: [
        { label: "My Trips", href: "/trips" },
        { label: "Reservation", href: "/holiday/reservation" },
        { label: "Account", href: "/account" },
      ],
    },
    {
      title: "TripMind",
      links: [{ label: "About", href: "/about" }],
    },
  ],
} as const;
