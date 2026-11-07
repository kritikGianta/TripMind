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

export type Reference = { id: string; citation: string; url: string; checkedOn: string };

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
    "Travellers make two kinds of decisions: quickly book one thing, a flight or a hotel, or coordinate several into one journey. When they plan across products, they piece together flights, stays, prices and policies across separate searches. Comparisons get lost, the true total cost is hard to judge, and the work continues after booking. AI can reduce that effort, but it must not block ordinary booking or take decisions away from the traveller.",
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
  "Book a flight on its own, without AI and without a hotel.",
  "Book a stay on its own, without AI and without a flight.",
  "Plan and book a flight and a stay together as one connected trip.",
  "Keep every booking in one place, and add the missing piece later.",
  "Show the full known price, and say clearly what the data does not include.",
  "Stay correct under failure: last seat, retries, payment errors, expired holds.",
  "Let AI help with searching and explaining, while the traveller makes every decision.",
  "Adapt to a new dataset or problem statement in hours, through configuration.",
];

// ── 6 · Solution: three ways to book ──────────────────────────────────────────────────────────

export const bookingModes: Capability[] = [
  {
    name: "Book a flight",
    detail: "Structured search, filters and comparison; hold, pay and confirm.",
    status: "planned",
  },
  {
    name: "Book a stay",
    detail: "Search by city, dates and guests; the stay price is validated before payment.",
    status: "planned",
  },
  {
    name: "Plan the whole trip",
    detail: "A form or a sentence produces ranked flight + hotel bundles that book through the same engine.",
    status: "planned",
  },
];

// ── 7 · How TripMind differs ──────────────────────────────────────────────────────────────────

export const differentiators: Array<{ typical: string; tripmind: string; status: Status }> = [
  { typical: "Flights and hotels sorted separately", tripmind: "Ranks complete, feasible flight + stay bundles", status: "planned" },
  { typical: "A headline price", tripmind: "An itemised price ledger that marks unknown fees", status: "planned" },
  { typical: "Filters and shortlists lost on navigation", tripmind: "A persistent trip record of intent, picks and rejections", status: "planned" },
  { typical: "Confirmation is the end", tripmind: "Recovery: rebuilds the trip when a flight is disrupted", status: "planned" },
  { typical: "Chatbot that can invent facts", tripmind: "AI grounded in data; it suggests, the traveller decides", status: "planned" },
  { typical: "Bundle-only or AI-only flows", tripmind: "Every product bookable on its own, with AI switched off", status: "planned" },
];

// ── 8 · Implementation and workflow ───────────────────────────────────────────────────────────

export const architecture = {
  layers: [
    { name: "Web app", detail: "Next.js + TypeScript; types generated from the API contract" },
    { name: "API", detail: "FastAPI modular monolith: routers → services → domain rules → repositories" },
    { name: "Data", detail: "PostgreSQL as the source of truth; Alembic migrations" },
    { name: "Plug-ins", detail: "AI providers, ranking models and cache behind interfaces and flags" },
  ],
  workflow: [
    "Import the dataset",
    "Search",
    "Compare and rank",
    "Hold inventory",
    "Pay (simulated)",
    "Confirm",
    "My Trips",
    "Recover from disruption",
  ],
};

export const capabilities: Capability[] = [
  { name: "Accounts and sessions", detail: "Argon2id passwords, httpOnly cookie sessions, rotating refresh tokens", status: "live" },
  { name: "Audit trail", detail: "Every sign-in success and failure recorded with a request ID", status: "live" },
  { name: "Error contract", detail: "One error format with stable codes; request ID shown to users", status: "live" },
  { name: "Health, readiness, metrics", detail: "/health, /ready and Prometheus /metrics", status: "live" },
  { name: "Feature flags", detail: "Modules switched on or off by configuration", status: "live" },
  { name: "One-command stack", detail: "Docker Compose: database, migrations, API, web", status: "live" },
  { name: "Data ingestion", detail: "Profile, map, validate, quarantine and report on any supplied ZIP", status: "live" },
  { name: "Flight and hotel search", detail: "Filter registry, offers with legs, price ledger", status: "planned" },
  { name: "Booking engine", detail: "Holds, idempotency, payment simulator, travellers, My Trips", status: "planned" },
  { name: "Connected-trip planner", detail: "Bundles, ranking, Journey Confidence Report", status: "planned" },
  { name: "Disruption recovery", detail: "Item-level rebooking with traveller approval", status: "planned" },
  { name: "AI assistant", detail: "Natural-language search, grounded answers, group planning", status: "planned" },
  { name: "Monitoring dashboards", detail: "Prometheus + Grafana + tracing", status: "planned" },
];

// ── 9 · Data handling ─────────────────────────────────────────────────────────────────────────

export const dataPipeline = {
  steps: [
    { name: "Profile", detail: "Every file and column described; a draft mapping is suggested" },
    { name: "Map", detail: "A YAML file maps the supplier's columns to TripMind fields" },
    { name: "Normalise", detail: "Codes, city aliases, local time to UTC, money as exact minor units" },
    { name: "Validate", detail: "Required fields, ranges, references between files, impossible times" },
    { name: "Quarantine", detail: "Bad rows are kept with the reason and the original values" },
    { name: "Publish", detail: "New, changed and retired rows applied in one transaction" },
    { name: "Report", detail: "Per file: read, accepted, rejected, inserted, updated, retired" },
  ],
  principles: [
    "Missing data is shown as \"not provided\", never guessed.",
    "Demo data is generated as files and imported through the same pipeline, so swapping in the real dataset is a configuration change.",
    "Re-importing the same file changes nothing; rows missing from a newer file are retired, not deleted.",
    "If too many rows fail, nothing is published: a wrong mapping cannot corrupt the catalog.",
  ],
  status: "live" as Status,
};

// ── 10 · AI boundaries ────────────────────────────────────────────────────────────────────────

export const aiBoundaries = {
  allowed: [
    "Turn a sentence into search criteria, and ask when something is missing",
    "Explain why an option ranked where it did, using its real values",
    "Answer questions from supplied documents, citing them",
    "Suggest alternatives from available inventory",
    "Prepare a booking draft for the traveller to review",
  ],
  notAllowed: [
    "Invent prices, availability or policies",
    "Book, pay, cancel or change anything without the traveller's confirmation",
    "Be required for ordinary flight or hotel booking",
    "Receive travellers' personal details",
  ],
  fallback:
    "Free hosted models are tried in order, with timeouts. If all are unavailable, rule-based parsing and templates take over and booking continues normally.",
  status: "planned" as Status,
};

// ── 11 · Edge cases ───────────────────────────────────────────────────────────────────────────

export const edgeCases: Capability[] = [
  { name: "Same email signs up twice", detail: "Rejected with a clear message; a database constraint guards simultaneous attempts", status: "live" },
  { name: "Password guessing", detail: "Sign-in attempts are rate-limited per client", status: "live" },
  { name: "Probing for registered emails", detail: "Unknown email and wrong password look identical and take the same time", status: "live" },
  { name: "Stolen session token reused", detail: "Reuse is detected and every session from that sign-in is ended", status: "live" },
  { name: "Session expires mid-use", detail: "Renewed silently once; otherwise the user is asked to sign in again", status: "live" },
  { name: "Malicious redirect link", detail: "Only TripMind pages are accepted as post-sign-in destinations", status: "live" },
  { name: "Two people book the last seat", detail: "Atomic stock update: exactly one succeeds", status: "planned" },
  { name: "Double-click or retry on pay", detail: "Idempotency keys return the first result", status: "planned" },
  { name: "Payment fails or the hold expires", detail: "Retry within the hold, or stock is released", status: "planned" },
  { name: "Flight confirmed but hotel fails", detail: "Shown as partial with a recovery path, never as fully confirmed", status: "planned" },
  { name: "AI provider down or rate-limited", detail: "Next provider, then rule-based fallback", status: "planned" },
  { name: "Bad rows in the dataset", detail: "Quarantined with a reason and counted in the import report", status: "live" },
  { name: "Flight lands after midnight in another timezone", detail: "Local times converted with each airport's timezone; arrival rolls to the next day", status: "live" },
  { name: "Misspelt or renamed city", detail: "Aliases (Bombay, Bangalore) and fuzzy matching, each match listed in the report", status: "live" },
  { name: "Price missing in the data", detail: "Shown as browse-only; no price is invented", status: "live" },
];

// ── 12 · Proof (only measured results) ────────────────────────────────────────────────────────

export const proof = {
  measured: [
    { value: "67", label: "automated backend tests passing on both SQLite and PostgreSQL", measuredOn: "7 Nov 2026" },
    { value: "18.6 s", label: "to validate and publish 23,841 synthetic flight rows plus hotels and rooms in Docker; 98 deliberately broken rows quarantined with reasons", measuredOn: "7 Nov 2026" },
  ],
  demoScript: [
    "Sign in with one click as the demo traveller",
    "Book a flight on its own, then a hotel on its own",
    "Plan a connected trip and compare bundles",
    "Inject a flight cancellation and approve the recovery",
    "Show the monitoring dashboard: one seat, many buyers, one winner",
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
    "Contribution per booking = net commission or licence share − payment cost − support cost − variable cloud and AI cost − refunds",
  validate: ["Single-product conversion", "Multi-product attach rate", "Support contacts per booking", "Time to shortlist"],
  note: "A hypothesis to test with a pilot partner. No revenue figures are claimed.",
};

// ── 14 · Limits and what is next ─────────────────────────────────────────────────────────────

export const limits = {
  today: [
    "Inventory comes from static files; nothing is live availability.",
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
