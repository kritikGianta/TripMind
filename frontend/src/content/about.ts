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
  { id: "implementation", title: "Built with", heading: "What it is built with, and why" },
  { id: "edge-cases", title: "Edge cases being solved", heading: "What happens when things go wrong" },
  { id: "business", title: "Business model", heading: "Who pays, and for what" },
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
    area: "API",
    choice: "Python 3.12 and FastAPI",
    why: "Requests are checked from type hints before our code runs, and the API describes itself, which generates the website's types.",
    insteadOf: "Django is heavier for a pure API.",
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
    area: "Shared state",
    choice: "Redis 7.4",
    why: "Fast shared memory for two things: rate limits and job locks, so several copies of the API agree. It is optional: limits fail open and locks fail closed.",
    insteadOf: "Memory inside each server copy is not shared, and database tables would add load to the source of truth.",
  },
  {
    area: "Background jobs",
    choice: "One worker process",
    why: "Releases bookings that were never confirmed, re-checks price alerts and clears old data, each job under a Redis lock so it never runs twice.",
    insteadOf: "Celery and a message broker add moving parts for three jobs.",
  },
  {
    area: "Running it",
    choice: "Docker Compose",
    why: "The whole stack, data included, starts with one command on any machine.",
    insteadOf: "Kubernetes is more than one machine needs.",
  },
];

// ── 11 · Edge cases: the important ones ───────────────────────────────────────────────────────

export const edgeCaseGroups: Group[] = [
  {
    name: "Two people, one seat",
    items: ["Two people book the last seat or room", "Double click or retry on Confirm", "Cancel only part of a booking"],
    summary: "The database lets exactly one booking win, a retry returns the first result, and nothing is confirmed that is not really free.",
    status: "live",
  },
  {
    name: "The airline has other plans",
    items: ["Flight cancelled", "Long delay"],
    summary: "Cancellations and delays of 3 hours or more offer rebooking or a refund. Only the affected item changes, and the traveller chooses.",
    status: "live",
  },
  {
    name: "A holiday that cannot be built",
    items: ["Budget too small", "No flight or no free rooms", "A change that breaks a rule"],
    summary: "TripMind says why: the reason for no package, the cheapest total with a suggestion, or the rule a change would break.",
    status: "live",
  },
];

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
