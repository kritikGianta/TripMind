/**
 * About page = presentation deck. This file is its single source of truth.
 *
 * Rules (see PROJECT_MEMORY.md, Section 9):
 * 1. Every external figure appears only if it was checked against its source (`checkedOn`).
 * 2. Every product capability carries a status. "live" means built, tested and running today;
 *    anything else is "planned". Update the status in the same change that ships the feature.
 * 3. The problem statement is our working statement until the official one is released on 13 Nov.
 * 4. The business model is a hypothesis; no revenue figures are invented.
 */

export type Status = "live" | "planned";

export type Stat = { value: string; label: string };

export type CaseStudy = {
  source: string;
  title: string;
  date: string;
  base: string;
  stats: Stat[];
  quote?: string;
  takeaway: string;
  referenceId: string;
};

export type Capability = { name: string; detail: string; status: Status };

/** Several capabilities or cases told as one group, with a summary underneath. */
export type Group = { name: string; items: string[]; summary: string; status: Status };

export type WorkflowNode = { label: string; step: number; tag?: "AI" | "Models" };

/** A part of the system in the request diagram; `steps` are the calls that pass through it. */
export type FlowNode = { label: string; steps: number[]; tag?: "AI" | "Models" };

export type StackItem ={ area: string; choice: string; why: string; insteadOf?: string };

export type Reference = { id: string; citation: string; url: string; checkedOn: string };

// ── Scene headings, in presentation order ─────────────────────────────────────────────────────

export const scenes = [
  { id: "thought", title: "Opening thought" },
  { id: "case-studies", title: "Case studies", heading: "What the research says about how people book travel" },
  { id: "problem", title: "Problem statement", heading: "Planning a trip is still a puzzle the traveller assembles by hand" },
  { id: "title", title: "Project" },
  { id: "objectives", title: "Objectives", heading: "What TripMind must do" },
  {
    id: "solution",
    title: "The solution",
    heading: "Three ways to book, one platform underneath",
    lead: "Each mode works on its own. All three share the same search, pricing, booking engine and My Trips.",
  },
  { id: "difference", title: "How it differs", heading: "Compared with a typical booking flow" },
  {
    id: "workflow",
    title: "How it works",
    heading: "One trip, from the first click to the way home",
    lead: "Keep scrolling: each step lights up the part of TripMind doing the work.",
  },
  {
    id: "under-the-hood",
    title: "Under the hood",
    heading: "How a request travels through TripMind",
    lead: "Keep scrolling: each call lights up the parts it passes through, hop by hop.",
  },
  { id: "implementation", title: "Built with", heading: "What it is built with, and why" },
  { id: "ai", title: "Rules, not AI", heading: "Every package is checked. Nothing is guessed." },
  { id: "edge-cases", title: "Edge cases being solved", heading: "What happens when things go wrong" },
  { id: "proof", title: "Live demo and proof", heading: "Measured, not claimed" },
  { id: "business", title: "Business model", heading: "Who pays, and for what" },
  { id: "limits", title: "Limits and what is next", heading: "What this prototype is, and is not" },
  { id: "closing", title: "The thought, explained" },
  {
    id: "references",
    title: "References",
    heading: "Sources",
    lead: "Each figure in this deck was checked against its source on the date shown.",
  },
] as const;

// ── Paintings used in the presentation (public domain, as stated on Wikimedia Commons) ─────────

export const artwork = {
  wanderer: { src: "/about/wanderer.webp", title: "Wanderer above the Sea of Fog", artist: "Caspar David Friedrich", year: "1818", page: "https://commons.wikimedia.org/wiki/File:Caspar_David_Friedrich_-_Wanderer_above_the_Sea_of_Fog.jpeg" },
  temeraire: { src: "/about/temeraire.webp", title: "The Fighting Temeraire", artist: "J. M. W. Turner", year: "1839", page: "https://commons.wikimedia.org/wiki/File:The_Fighting_Temeraire,_JMW_Turner,_National_Gallery.jpg" },
  railway: { src: "/about/railway.webp", title: "Rain, Steam and Speed", artist: "J. M. W. Turner", year: "1844", page: "https://commons.wikimedia.org/wiki/File:Turner_-_Rain,_Steam_and_Speed_-_National_Gallery_file.jpg" },
  sierra: { src: "/about/sierra.webp", title: "Among the Sierra Nevada, California", artist: "Albert Bierstadt", year: "1868", page: "https://commons.wikimedia.org/wiki/File:Albert_Bierstadt_-_Among_the_Sierra_Nevada,_California_-_Google_Art_Project.jpg" },
  voyage: { src: "/about/voyage.webp", title: "The Voyage of Life: Youth", artist: "Thomas Cole", year: "1842", page: "https://commons.wikimedia.org/wiki/File:Thomas_Cole_-_The_Voyage_of_Life_Youth,_1842_(National_Gallery_of_Art).jpg" },
  wave: { src: "/about/wave.webp", title: "The Ninth Wave", artist: "Ivan Aivazovsky", year: "1850", page: "https://commons.wikimedia.org/wiki/File:Hovhannes_Aivazovsky_-_The_Ninth_Wave_-_Google_Art_Project.jpg" },
  map: { src: "/about/map.webp", title: "Typus Orbis Terrarum", artist: "Abraham Ortelius", year: "1570", page: "https://commons.wikimedia.org/wiki/File:OrteliusWorldMap1570.jpg" },
} as const;

export type ArtName = keyof typeof artwork;

// ── 1 · Opening thought (deliberately unexplained until the last slide) ───────────────────────

export const openingQuote = {
  text: "Nobody travels in pieces. So why do we book that way?",
  attribution: "TripMind",
};

// ── 2 · Case studies (figures verified on the date in `references`) ────────────────────────────

export const caseStudies: CaseStudy[] = [
  {
    source: "McKinsey & Company",
    title: "The State of Aviation 2025",
    date: "May 2025",
    base: "Consumer survey of 7,000 people, March 2025",
    stats: [
      { value: "39%", label: "find it hard to find the best price" },
      { value: "36%", label: "cite hidden fees or lack of transparency" },
      { value: "29%", label: "cite limited flexibility for refunds and changes" },
      { value: "24%", label: "find comparing offers complex" },
      { value: "21%", label: "find the booking process too long" },
    ],
    takeaway: "The pain is price clarity and comparison, not just the booking form.",
    referenceId: "mckinsey-aviation-2025",
  },
  {
    source: "McKinsey & Company with Skift",
    title: "Winning hearts in an age of infinite travel choices",
    date: "22 September 2026",
    base: "Survey of 1,000+ US travellers and booking diaries from 26 participants",
    stats: [
      { value: "45 → 65", label: "touchpoints in the travel journey, 2018 → 2026" },
      { value: "Half", label: "of travellers changed a booked stay after seeing a better option" },
    ],
    quote: "Booking confirmation has become a waypoint instead of a finish line.",
    takeaway: "The journey keeps going after the booking, so the product has to as well.",
    referenceId: "mckinsey-winning-hearts-2026",
  },
  {
    source: "Booking.com",
    title: "The Global AI Sentiment Report",
    date: "23 July 2025",
    base: "37,000+ consumers across 33 markets",
    stats: [
      { value: "89%", label: "want to use AI in future travel planning" },
      { value: "6%", label: "fully trust AI" },
      { value: "12%", label: "are comfortable with AI making decisions on its own" },
    ],
    takeaway: "Travellers want AI's help, but they want to make the final call themselves.",
    referenceId: "booking-ai-sentiment-2025",
  },
  {
    source: "Booking Holdings",
    title: "Third-quarter 2026 results",
    date: "3 November 2026",
    base: "Company-reported results",
    stats: [
      { value: "345M", label: "room nights in the quarter, up 7% year over year" },
      { value: "$54.5B", label: "gross bookings, up 10% year over year" },
    ],
    quote:
      "As AI transforms the ways to discover, plan, and book travel, we continue to make progress integrating AI across our brands, developing AI-native experiences, and collaborating with industry-leading AI platforms.",
    takeaway: "Industry scale is real, and the stated direction is AI woven into the whole journey.",
    referenceId: "bkng-q3-2026",
  },
];

// ── 3 · Problem statement ──────────────────────────────────────────────────────────────────────

export const problemStatement = {
  label: "Working problem statement · replaced by the official statement on 13 November",
  text:
    "Travellers make two kinds of decisions: quickly book one thing, a flight or a hotel, or coordinate several into one journey. When they plan across products, they piece together flights, stays, prices and policies across separate searches. Comparisons get lost, the true total cost is hard to judge, and the work continues after booking. TripMind takes that effort away with plain rules that build and check the whole trip, while the traveller still makes every decision.",
  pains: [
    { title: "Fragmented discovery", detail: "Flights and stays are searched separately and combined by hand." },
    { title: "Decision overload", detail: "Long lists with no explanation of the trade-offs." },
    { title: "Unclear total cost", detail: "Headline prices hide fees and missing policy details." },
    { title: "Lost context", detail: "Coming back to a plan means starting the research again." },
    { title: "After-booking uncertainty", detail: "Changes and disruptions arrive after confirmation." },
  ],
};

// ── 4 · Title ──────────────────────────────────────────────────────────────────────────────────

export const titleMeaning = {
  name: "TripMind",
  parts: [
    { word: "Trip", meaning: "the whole journey: flights, stays and everything after booking" },
    { word: "Mind", meaning: "a system that remembers that journey and reasons across it" },
  ],
};

// ── 5 · Objectives ─────────────────────────────────────────────────────────────────────────────

export const objectives: string[] = [
  "Book a flight on its own, or a stay on its own.",
  "Plan a trip: a flight and a stay, ranked together with reasons.",
  "Build a whole holiday: the app chooses the cities and adds flights, hotels, transfers and attractions.",
  "Make every package pass every travel rule, and check it again after each change.",
  "Show the total against the budget, and say what to change when nothing fits.",
  "Give every confirmed trip a 10-digit reservation number that opens it any time.",
  "Stay correct under pressure: the last seat or room is never sold twice.",
  "Use no AI inside the app: plain rules that anyone can read and check.",
];

// ── 6 · Solution: ways to book ───────────────────────────────────────────────────────────────

export const bookingModes: Capability[] = [
  {
    name: "Book a flight or a stay",
    detail: "Search, compare and confirm one thing on its own; only free seats and rooms are offered.",
    status: "live",
  },
  {
    name: "Plan a trip",
    detail: "Flights both ways plus a hotel, combined, checked to fit and ranked by price, time, stay and convenience.",
    status: "live",
  },
  {
    name: "Book my holiday",
    detail: "From a form or one sentence: TripMind picks the cities and builds the cheapest, fastest and best-rated packages.",
    status: "live",
  },
];

// ── 7 · How TripMind differs ──────────────────────────────────────────────────────────────────

export const differentiators: Array<{ typical: string; tripmind: string; status: Status }> = [
  { typical: "Ready-made packages, or a flight then a hotel", tripmind: "Builds the whole holiday and chooses the cities", status: "live" },
  { typical: "Parts that may not fit together", tripmind: "Every rule checked: landing, pickups, rooms, opening hours", status: "live" },
  { typical: "A change breaks the trip silently", tripmind: "Every change is checked again, or refused with the reason", status: "live" },
  { typical: "A headline price", tripmind: "Every price line by line, and the total against the budget", status: "live" },
  { typical: "Confirmation is the end", tripmind: "A 10-digit reservation, My Trips, and recovery when plans change", status: "live" },
  { typical: "A chatbot that can invent facts", tripmind: "No AI: rules read your sentence and fill the form", status: "live" },
];

// ── 8 · How it works (a scroll-driven diagram) ───────────────────────────────────────────────

export const workflow = {
  steps: [
    {
      title: "Open TripMind",
      detail: "The traveller lands on the website. No sign-up: a private guest session starts by itself, so trips and bookings are kept.",
    },
    {
      title: "Choose a way in",
      detail:
        "Book a flight, book a stay, plan a trip, or book a whole holiday. For a holiday you can type a sentence such as “2 adults and a 6 year old from Bengaluru to Japan on 10 April for 6 nights under 3.5 lakh”: plain rules fill in the form.",
    },
    {
      title: "Choose the cities",
      detail:
        "For a holiday, TripMind tries every way to split the nights across the country's cities, at least 2 nights each, moving only where a train or bus runs.",
    },
    {
      title: "Fill in the pieces",
      detail:
        "Flights that land on the start date and leave on the last day, a hotel per city that fits the family and has rooms every night, airport transfers, the train between cities, and 1-2 attractions on each full day.",
    },
    {
      title: "Check every rule",
      detail:
        "One rule checker tests every rule in the problem statement, then the cheapest, fastest and best-rated packages are shown with the total against the budget.",
    },
    {
      title: "Change and confirm",
      detail:
        "Swap a hotel or a flight, add or remove attractions: every change is checked again. Confirming reserves the seats and rooms in one step and gives a 10-digit reservation number.",
    },
    {
      title: "My Trips, and friends",
      detail:
        "Holidays and bookings are kept in My Trips. A plan can be shared: friends vote Love, OK or No, set their budgets, and the organiser books.",
    },
    {
      title: "When plans change",
      detail:
        "If the airline cancels, the options are saved and the traveller chooses: another flight or a refund, and for a delay, keeping it. Only the affected item is replaced.",
    },
  ],
  lanes: [
    { name: "Front door", nodes: [{ label: "Open TripMind", step: 0 }] },
    {
      name: "Ways in",
      nodes: [
        { label: "Type a sentence", step: 1 },
        { label: "Book a flight", step: 1 },
        { label: "Book a stay", step: 1 },
        { label: "Plan a trip", step: 1 },
        { label: "Book my holiday", step: 1 },
      ],
    },
    {
      name: "Behind the scenes",
      nodes: [
        { label: "City plans", step: 2 },
        { label: "Flights, hotels, transfers", step: 3 },
        { label: "Attractions", step: 3 },
        { label: "Rule checker", step: 4 },
        { label: "Confirm", step: 5 },
      ],
    },
    {
      name: "Your trip",
      nodes: [
        { label: "Reservation number", step: 5 },
        { label: "My Trips", step: 6 },
        { label: "Plan with friends", step: 6 },
        { label: "Recovery", step: 7 },
      ],
    },
  ] satisfies Array<{ name: string; nodes: WorkflowNode[] }>,
  note: "Everything here runs on plain rules. There is no AI inside the app.",
};

// ── 9 · Under the hood: the real calls, and every part each one passes through ─────────────────

export const requestFlow = {
  calls: [
    {
      title: "Loading the data",
      call: "python -m app.cli holiday load, on every start",
      hops: ["Official JSON pack", "Our extension, same schema", "PostgreSQL"],
      detail:
        "A one-shot step reads the official data pack and our extra data in the same schema, and loads them into one catalog in one transaction. IDs are stable, so loading twice changes nothing, and reservations already made are kept.",
    },
    {
      title: "A page opens",
      call: "GET /plan, a page",
      hops: ["Browser", "Next.js server", "Finished HTML"],
      detail:
        "Next.js renders the page on the server and sends finished HTML. The page then fetches its data from /api on the same address.",
    },
    {
      title: "Every call passes the same checks",
      call: "Any /api/v1/… request",
      hops: ["Browser", "Next.js /api proxy", "FastAPI checks", "Redis"],
      detail:
        "The proxy forwards the call to the API inside Docker. The API gives each call a request ID, adds security headers and refuses oversized bodies. A guest session is read from an httpOnly cookie, and rate limits are counted in Redis.",
    },
    {
      title: "Type a sentence",
      call: "POST /api/v1/holiday/parse",
      hops: ["Holiday module", "Rules", "Catalog places"],
      detail:
        "Regular-expression rules read the departure city, country, date, nights, travellers, children's ages and budget. Places are matched against the data, so a place we do not have is never invented. The answer only fills the form.",
    },
    {
      title: "Build the packages",
      call: "POST /api/v1/holiday/packages",
      hops: ["Holiday engine", "PostgreSQL catalog", "Rule checker", "Saved packages"],
      detail:
        "The engine loads the catalog once, tries every city plan, fills in flights, hotels, transfers and attractions, and keeps only packages that pass every rule. The cheapest, fastest and best-rated are saved, so they survive a restart.",
    },
    {
      title: "Change a package",
      call: "POST /api/v1/holiday/packages/{id}/changes",
      hops: ["Holiday service", "Rule checker", "PostgreSQL"],
      detail:
        "A new hotel or flight also moves the airport transfers. The whole package is checked again; a change that breaks a rule is refused with the reason, and nothing is saved.",
    },
    {
      title: "Confirm",
      call: "POST /api/v1/holiday/packages/{id}/confirm",
      hops: ["Holiday service", "One PostgreSQL transaction", "10-digit number"],
      detail:
        "Seats and rooms are taken with a conditional update, “reserved + wanted ≤ capacity”, so the last room is never sold twice. A secure random 10-digit number is stored with a unique rule, and confirming twice returns the same number.",
    },
    {
      title: "Open a reservation",
      call: "GET /api/v1/holiday/reservations/{number}",
      hops: ["Holiday service", "Indexed lookup", "Summary"],
      detail:
        "One query on an indexed, unique column finds the reservation; a wrong number gets “not found”. My Trips lists the traveller's own holidays the same way.",
    },
    {
      title: "Meanwhile, the worker",
      call: "python -m app.worker, with no web traffic",
      hops: ["Worker", "Redis lock", "PostgreSQL"],
      detail:
        "A separate process frees unpaid holds every 30 seconds, re-checks price alerts and deletes data past its retention date, each job under a Redis lock so it runs once.",
    },
  ],
  tiers: [
    {
      name: "Browser",
      nodes: [{ label: "Website", steps: [1, 2, 3, 4, 5, 6, 7] }],
    },
    {
      name: "Next.js server",
      nodes: [
        { label: "Page rendering", steps: [1] },
        { label: "/api proxy", steps: [2, 3, 4, 5, 6, 7] },
      ],
    },
    {
      name: "API (FastAPI)",
      nodes: [
        { label: "Request ID, limits, session", steps: [2] },
        { label: "Quick request rules", steps: [3] },
        { label: "Holiday engine", steps: [4, 5] },
        { label: "Rule checker", steps: [4, 5, 6] },
        { label: "Reservations", steps: [6, 7] },
      ],
    },
    {
      name: "Stores",
      nodes: [
        { label: "PostgreSQL", steps: [0, 3, 4, 5, 6, 7, 8] },
        { label: "Redis", steps: [2, 8] },
      ],
    },
    {
      name: "Data",
      nodes: [
        { label: "Official data pack", steps: [0] },
        { label: "Extension, same schema", steps: [0] },
      ],
    },
    {
      name: "Alongside",
      nodes: [
        { label: "Data loader", steps: [0] },
        { label: "Worker", steps: [8] },
      ],
    },
  ] satisfies Array<{ name: string; nodes: FlowNode[] }>,
  note: "Lit parts are the ones the current call touches. Redis and monitoring are optional: without them, TripMind still works.",
};

// ── 10 · Built with: each choice and the reason for it ───────────────────────────────────────

export const techStack: StackItem[] = [
  {
    area: "Web app",
    choice: "Next.js 16, React 19, TypeScript",
    why: "Pages are rendered on the server, so they open fast, and the built-in proxy puts the API on the same address, so sessions can use secure httpOnly cookies.",
    insteadOf: "A plain React single-page app renders only in the browser and would need cross-site API calls.",
  },
  {
    area: "Design",
    choice: "Tailwind CSS 4 and shadcn/ui",
    why: "Accessible components whose code we own, styled from shared design tokens, so every page matches.",
    insteadOf: "Bootstrap or Material UI are harder to reshape into our own look.",
  },
  {
    area: "Data fetching",
    choice: "TanStack Query",
    why: "Caching, retries and loading states for every API call; the website's types are generated from the API, so both always agree.",
    insteadOf: "Hand-written fetch calls in every component repeat the same mistakes.",
  },
  {
    area: "API",
    choice: "Python 3.12 and FastAPI",
    why: "Requests are checked from type hints before our code runs, and the API describes itself, which generates the website's types.",
    insteadOf: "Django is heavier for a pure API.",
  },
  {
    area: "Holiday engine",
    choice: "Plain Python rules",
    why: "One rule checker holds every travel rule from the problem statement, so each rule reads like the handout and can be changed in one line.",
    insteadOf: "An AI or a trained model, which the rules forbid and which nobody could check line by line.",
  },
  {
    area: "Database access",
    choice: "SQLAlchemy 2 and Alembic",
    why: "Typed queries that run on PostgreSQL, and on SQLite for quick tests, with every schema change versioned.",
    insteadOf: "Raw SQL strings scattered through the code.",
  },
  {
    area: "Database",
    choice: "PostgreSQL 16",
    why: "Transactions and conditional updates let exactly one buyer win the last seat or room, partial unique indexes allow one passenger per seat, and a failed schema change rolls back cleanly.",
    insteadOf: "MySQL has no partial indexes and commits schema changes implicitly; MongoDB suits loose documents better than tightly linked bookings and seats.",
  },
  {
    area: "Data",
    choice: "The official pack, plus our extension in the same schema",
    why: "The official files are loaded as they are; our seeded generator adds more dates and five more countries with exactly the same fields.",
    insteadOf: "Changing the official files, which the rules forbid.",
  },
  {
    area: "Shared state",
    choice: "Redis 7.4",
    why: "Fast shared memory for rate limits, sign-in lockouts and job locks, so several copies of the API agree. It is optional: limits fail open and locks fail closed.",
    insteadOf: "Memory inside each server copy is not shared, and database tables would add load to the source of truth.",
  },
  {
    area: "Background jobs",
    choice: "One worker process",
    why: "Frees unpaid holds, re-checks price alerts and applies retention, each job under a Redis lock so it never runs twice.",
    insteadOf: "Celery and a message broker add moving parts for three jobs.",
  },
  {
    area: "Security",
    choice: "Guest sessions, Argon2id, short-lived tokens in httpOnly cookies",
    why: "No sign-up needed, yet every trip belongs to someone; sessions that page scripts cannot read, and memory-hard password hashing for staff.",
    insteadOf: "Tokens kept in browser storage, where any injected script can read them.",
  },
  {
    area: "Monitoring",
    choice: "Prometheus, Grafana, OpenTelemetry, Jaeger",
    why: "Open standards, with metrics, dashboards, alert rules and traces kept as code. All of it is optional.",
    insteadOf: "A paid hosted monitoring service.",
  },
  {
    area: "Running it",
    choice: "Docker Compose",
    why: "The whole stack, data included, starts with one command on any machine.",
    insteadOf: "Kubernetes is more than one machine needs.",
  },
  {
    area: "Quality",
    choice: "pytest, ruff, mypy, import-linter, GitHub Actions",
    why: "Tests through the real API on two databases, type checks, and a rule that fails the build when code crosses its layers.",
  },
];

export const capabilityGroups: Group[] = [
  {
    name: "Book my holiday",
    items: ["Request form", "Cities chosen by the app", "Every rule checked", "Day-by-day plan", "Total and budget", "JSON export", "Change hotel, flight, attractions", "10-digit reservation", "Budget too small", "Cheapest, fastest, best rated", "Quick request"],
    summary: "Every must-have, good-to-have and stretch feature of the problem: a complete package that passes every rule, changes that are checked again, and a reservation number that survives a restart.",
    status: "live",
  },
  {
    name: "Booking, for real",
    items: ["Flight and stay search", "Itemised prices", "Holds", "Confirm without payment", "Changes and cancellations", "Seats, bags and meals", "Promo codes"],
    summary: "Search flights and stays, see every price line by line, hold and confirm, then change or cancel a single item.",
    status: "live",
  },
  {
    name: "Plan and explore",
    items: ["Plan a trip", "Journey Confidence Report", "What the trip is missing", "Plan with friends", "Fare calendar", "Explore by budget", "Saved stays and price alerts"],
    summary: "Ranked flight and stay plans with reasons, group voting with budgets, and ways to find the cheapest day or where a budget can take you.",
    status: "live",
  },
  {
    name: "After booking",
    items: ["My Trips", "Disruption recovery", "Notifications", "Reviews", "Support requests", "Loyalty points", "Invoice"],
    summary: "Every trip and holiday in one place; when an airline cancels, the traveller chooses the fix.",
    status: "live",
  },
  {
    name: "Data",
    items: ["Official data pack", "Seven countries, eighteen cities", "Dates to May 2027", "Same schema throughout", "Loaded on every start"],
    summary: "The official pack, untouched, plus our extension with more dates and countries in exactly the same format, all in one catalog.",
    status: "live",
  },
  {
    name: "Accounts, safety and running it",
    items: ["Guest sessions", "Secure cookies", "Data export", "Audit trail", "Admin consoles", "Health checks", "Feature flags", "One-command start"],
    summary: "No sign-up for travellers, protected sessions, admin tools for disruptions and support, and every feature can be switched on or off.",
    status: "live",
  },
];

// ── 10 · Rules, not AI ────────────────────────────────────────────────────────────────────────

export const aiBoundaries = {
  allowed: [
    "Land on the start date at an airport that serves the first city",
    "Have a pickup at least 60 minutes after landing, inside service hours",
    "Fit the family in the rooms, with rooms free on every night",
    "Visit attractions in that night's city, open, with no overlaps",
    "Reach the airport at least 3 hours before the flight home",
  ],
  notAllowed: [
    "Call an AI or language model, in the cloud or on the laptop",
    "Invent a price, a seat, a room or a place",
    "Save a change that breaks a rule",
    "Sell the last seat or room twice",
  ],
  fallback:
    "A typed sentence is read by plain rules that match places against the data. Whatever they cannot read stays as it was in the form, and the traveller is told what is missing.",
  status: "live" as Status,
};

// ── 11 · Edge cases, in five families ──────────────────────────────────────────────────────

export const edgeCaseGroups: Group[] = [
  {
    name: "Your card, my seat",
    items: ["Two people book the last seat", "Two people pick the same seat", "Double click or retry on Pay", "Payment fails or the hold runs out", "Price changes during checkout", "Cancel only part of a booking", "Change a flight late"],
    summary: "The database lets exactly one buyer win, a retry returns the first result, and nobody pays for something they did not get.",
    status: "live",
  },
  {
    name: "The airline has other plans",
    items: ["Flight cancelled", "Short delay or long delay", "Disruption on an unpaid hold"],
    summary: "Short delays send a message; cancellations and delays of 3 hours or more offer rebooking or a refund. Only the affected item changes, and the traveller chooses.",
    status: "live",
  },
  {
    name: "Messy data",
    items: ["Broken rows", "Late arrivals across timezones", "Misspelt or renamed cities", "Missing prices", "Impossible connections", "Mixed currencies", "Dates in the past"],
    summary: "Nothing is guessed: bad rows are set aside with a reason, a missing price makes an item browse-only, and times and currencies are converted and labelled.",
    status: "live",
  },
  {
    name: "Someone pretending to be you",
    items: ["Same email twice", "Password guessing", "Probing for accounts", "Stolen session reused", "Session expires", "Malicious redirect links"],
    summary: "Limits and lockouts stop guessing, a stolen session ends every session from that sign-in, and the site only ever sends you to its own pages.",
    status: "live",
  },
  {
    name: "A holiday that cannot be built",
    items: ["Dates outside the data", "Budget too small", "No flight lands that day", "No free rooms", "A change that breaks a rule"],
    summary: "TripMind says why: the reason for no package, the cheapest total with a suggestion, or the rule a change would break.",
    status: "live",
  },
];

// ── 12 · Proof (only measured results) ────────────────────────────────────────────────────────

export const proof = {
  measured: [
    { value: "20 → 1", label: "buyers racing for one seat on PostgreSQL (real threads): one booked, 19 told it sold out", measuredOn: "9 Nov 2026" },
    { value: "910 / 0", label: "synthetic requests from 8 virtual users in 46 s / server errors; search p95 0.47 s on a laptop in Docker", measuredOn: "7 Nov 2026" },
    { value: "3 / 0", label: "packages built for the handout's Menon family request / rules broken by any of them", measuredOn: "13 Nov 2026" },
    { value: "212", label: "automated backend tests passing on both SQLite and PostgreSQL", measuredOn: "9 Nov 2026" },
  ],
  demoScript: [
    "Type the Menon request in one sentence and fill the form",
    "Compare the cheapest, fastest and best-rated packages day by day",
    "Change a hotel, remove an attraction, then confirm for a 10-digit number",
    "Open the reservation by its number, and see it in My Trips",
    "Inject a flight cancellation and approve the recovery",
    "Run the race test: 20 buyers, one seat, one winner",
  ],
};

// ── 13 · Business model (hypothesis) ──────────────────────────────────────────────────────────

export const businessModel = {
  positioning:
    "A B2B2C booking and journey layer that travel agencies, niche online travel agencies and corporate travel teams can embed or white-label.",
  streams: [
    { name: "SaaS subscription", payer: "Agencies and corporate travel teams", value: "Trip workspace, planning and analytics" },
    { name: "White-label licensing", payer: "Travel platforms", value: "Branded search, planning and recovery modules" },
    { name: "Transaction referrals", payer: "Suppliers, under contract", value: "Qualified, completed bookings" },
  ],
  unitEconomics:
    "Contribution per booking = net commission or licence share − payment cost − support cost − variable cloud cost − refunds",
  validate: ["Single-product conversion", "Multi-product attach rate", "Support contacts per booking", "Time to shortlist"],
  note: "A hypothesis to test with a pilot partner. No revenue figures are claimed.",
};

// ── 14 · Limits and what is next ─────────────────────────────────────────────────────────────

export const limits = {
  today: [
    "Inventory comes from the official files and our synthetic extension; nothing is live availability.",
    "Payments are simulated; no money moves.",
    "No airline or hotel supplier integrations.",
  ],
  next: [
    "Supplier adapters, with compensation steps for bookings that span systems",
    "Separate scaling for search and planning when load requires it",
    "Real payments, privacy and consumer-protection review before any launch",
  ],
};

// ── 15 · Closing: the opening thought, explained ─────────────────────────────────────────────

export const closing = {
  quote: openingQuote.text,
  pieces: [
    { piece: "Searching in pieces", answer: "One trip record holds intent, options and decisions." },
    { piece: "Paying in pieces", answer: "One price ledger for the whole journey, unknowns included." },
    { piece: "Travelling in pieces", answer: "When something breaks, TripMind rebuilds the trip, and the traveller approves." },
  ],
  line: "TripMind keeps the journey in one piece, from the first search to arrival.",
};

// ── 16 · References ──────────────────────────────────────────────────────────────────────────

export const references: Reference[] = [
  {
    id: "mckinsey-aviation-2025",
    citation: "McKinsey & Company, The State of Aviation 2025 (May 2025)",
    url: "https://www.mckinsey.com/~/media/mckinsey/industries/travel/our%20insights/the%20state%20of%20aviation%202025/the-state-of-aviation-2025-final.pdf",
    checkedOn: "7 Nov 2026",
  },
  {
    id: "mckinsey-winning-hearts-2026",
    citation: "McKinsey & Company and Skift, Winning hearts in an age of infinite travel choices (22 Sep 2026)",
    url: "https://www.mckinsey.com/industries/travel/our-insights/winning-hearts-in-an-age-of-infinite-travel-choices/",
    checkedOn: "7 Nov 2026",
  },
  {
    id: "booking-ai-sentiment-2025",
    citation: "Booking.com, The Global AI Sentiment Report (23 Jul 2025)",
    url: "https://news.booking.com/bookingcom-releases-the-global-ai-sentiment-report/",
    checkedOn: "7 Nov 2026",
  },
  {
    id: "bkng-q3-2026",
    citation: "Booking Holdings, Third Quarter 2026 Financial Results (3 Nov 2026)",
    url: "https://www.sec.gov/Archives/edgar/data/1075531/000107553126000044/q3-26bkngearningsrelease.htm",
    checkedOn: "7 Nov 2026",
  },
];
