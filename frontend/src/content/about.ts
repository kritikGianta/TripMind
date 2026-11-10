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
  { id: "ai", title: "AI boundaries", heading: "AI suggests. The traveller decides." },
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
    status: "live",
  },
  {
    name: "Book a stay",
    detail: "Search by city, dates and guests; the stay price is validated before payment.",
    status: "live",
  },
  {
    name: "Plan the whole trip",
    detail: "A form or a sentence produces ranked flight + hotel bundles that book through the same engine.",
    status: "live",
  },
];

// ── 7 · How TripMind differs ──────────────────────────────────────────────────────────────────

export const differentiators: Array<{ typical: string; tripmind: string; status: Status }> = [
  { typical: "Flights and hotels sorted separately", tripmind: "Ranks complete, feasible flight + stay bundles", status: "live" },
  { typical: "A headline price", tripmind: "An itemised price ledger that marks unknown fees", status: "live" },
  { typical: "Filters and shortlists lost on navigation", tripmind: "A persistent trip record of intent, picks and rejections", status: "live" },
  { typical: "Confirmation is the end", tripmind: "Recovery: rebuilds the trip when a flight is disrupted", status: "live" },
  { typical: "Chatbot that can invent facts", tripmind: "AI grounded in data; it suggests, the traveller decides", status: "live" },
  { typical: "Bundle-only or AI-only flows", tripmind: "Every product bookable on its own, with AI switched off", status: "live" },
];

// ── 8 · How it works (a scroll-driven diagram) ───────────────────────────────────────────────

export const workflow = {
  steps: [
    {
      title: "Open TripMind",
      detail: "The traveller lands on the website. Looking around needs no account; signing in is one step, and only needed to book.",
    },
    {
      title: "Choose a way in",
      detail:
        "Book a flight, book a stay, or plan the whole trip. Or type a sentence such as “2 of us, Delhi to Goa next Friday”: AI fills in the form, and simple rules do it when AI is off.",
    },
    {
      title: "Search",
      detail:
        "Flights, direct or with one stop, and stays that fit the whole party. Every price is shown line by line, and anything it does not include is marked.",
    },
    {
      title: "Rank and explain",
      detail:
        "Small models order the stays and label each fare as low, typical or high. For a whole trip, the planner builds complete flight and stay packages, scores them, and explains every score in a Journey Confidence Report.",
    },
    {
      title: "Hold",
      detail:
        "The chosen seat or room is held for 15 minutes in a single database step, so when two people want the last seat, exactly one gets it.",
    },
    {
      title: "Pay and confirm",
      detail:
        "Seat first, money second. A double click cannot charge twice, a declined card keeps the hold, and confirmation brings an invoice and loyalty points. Card payments are simulated.",
    },
    {
      title: "My Trips, and friends",
      detail:
        "Every booking lands in one trip, which suggests the missing piece. A plan can be shared: friends vote Love, OK or No, set their budgets, and the organiser books.",
    },
    {
      title: "When plans change",
      detail:
        "If the airline cancels, the options are saved and the traveller chooses: another flight or a refund, and for a delay, keeping it. Ask TripMind answers from the real policies, and support requests are filed automatically.",
    },
  ],
  lanes: [
    { name: "Front door", nodes: [{ label: "Open TripMind", step: 0 }] },
    {
      name: "Ways in",
      nodes: [
        { label: "Type a sentence", step: 1, tag: "AI" },
        { label: "Book a flight", step: 1 },
        { label: "Book a stay", step: 1 },
        { label: "Plan the whole trip", step: 1 },
      ],
    },
    {
      name: "Behind the scenes",
      nodes: [
        { label: "Search", step: 2 },
        { label: "Rank and explain", step: 3, tag: "Models" },
        { label: "Hold 15 minutes", step: 4 },
        { label: "Pay", step: 5 },
        { label: "Confirm", step: 5 },
      ],
    },
    {
      name: "Your trip",
      nodes: [
        { label: "My Trips", step: 6 },
        { label: "Plan with friends", step: 6 },
        { label: "Ask TripMind", step: 7, tag: "AI" },
        { label: "Recovery", step: 7 },
      ],
    },
  ] satisfies Array<{ name: string; nodes: WorkflowNode[] }>,
  note: "AI and Models mark the optional helpers. Switch them all off and every step still works.",
};

// ── 9 · Under the hood: the real calls, and every part each one passes through ─────────────────

export const requestFlow = {
  calls: [
    {
      title: "A page opens",
      call: "GET /trips, a page",
      hops: ["Browser", "Next.js server", "Finished HTML"],
      detail:
        "Next.js renders the page on the server and sends finished HTML, so it appears before any script runs. The page then fetches its data from /api on the same address.",
    },
    {
      title: "Every call passes the same checks",
      call: "Any /api/v1/… request",
      hops: ["Browser", "Next.js /api proxy", "FastAPI checks", "Redis"],
      detail:
        "The proxy forwards the call to the API inside Docker, so the browser talks to one address and the sign-in cookies stay httpOnly. The API gives each call a request ID, returned in the X-Request-Id header and written on every log line, adds security headers and refuses oversized bodies. Sign-in is read from the tm_access cookie; if it has expired, the website refreshes it once and repeats the call. Rate limits are counted in Redis, so every copy of the API shares them.",
    },
    {
      title: "Type a sentence",
      call: "POST /api/v1/ai/parse-search",
      hops: ["AI module", "Redis cache", "Groq → Gemini → OpenRouter", "PostgreSQL catalog"],
      detail:
        "Emails, phone numbers and card-like numbers are removed before the text leaves TripMind. A repeated question is answered from the Redis cache; otherwise the providers are tried in order, each with a timeout, and one that fails is rested for a while. If none answers, a rule-based parser takes over. Place names are then matched against the catalog, so a city we do not have is reported missing, never invented. The answer only fills the form.",
    },
    {
      title: "Search",
      call: "GET /api/v1/flights/search, GET /api/v1/hotels/search",
      hops: ["Search", "PostgreSQL", "LightGBM models", "Priced results"],
      detail:
        "Search reads flights, stays, rooms and what is still free from PostgreSQL, and prices every line. On Indian domestic routes, a LightGBM model predicts the typical fare: 15% under it is labelled below typical, 15% over is above typical. A second LightGBM model orders the stays from stars, guest rating, nightly price, party size and how far ahead the stay is; without it, a fixed rule orders them.",
    },
    {
      title: "Plan the whole trip",
      call: "POST /api/v1/plans",
      hops: ["Planner", "Flight and stay search", "Scored packages", "PostgreSQL"],
      detail:
        "The planner runs the same flight and stay searches, combines them into complete packages, then scores and ranks them. The plan is saved with its Journey Confidence Report, so it can be reopened and shared with a group.",
    },
    {
      title: "Hold the seat",
      call: "POST /api/v1/bookings, with an Idempotency-Key",
      hops: ["Bookings", "One PostgreSQL transaction", "Hold for 15 minutes"],
      detail:
        "One transaction writes the booking, its items and the reservation. The seat is taken by a conditional update, “reserved + wanted ≤ capacity”: if no row changes, the seat has gone and the buyer is told so, which is why exactly one of 20 buyers wins the last seat. A retried call with the same Idempotency-Key returns the same booking, never a second one. The timeline event and the audit record are written in the same transaction.",
    },
    {
      title: "Pay and confirm",
      call: "POST /api/v1/bookings/{id}/payments, with an Idempotency-Key",
      hops: ["Bookings", "Row lock", "Simulated card", "One commit"],
      detail:
        "The booking row is locked first, so two clicks cannot pay at once, and a repeated key returns the earlier result without a second charge. An expired hold is refused. On success, one commit records the payment, confirms the booking, adds loyalty points, and writes the notification and the audit record. On a decline, the hold is kept until it expires. Payment counters move only after the commit.",
    },
    {
      title: "Ask TripMind",
      call: "POST /api/v1/ai/assistant",
      hops: ["BM25 help search", "Trip summary", "Groq → Gemini → OpenRouter", "Text classifier"],
      detail:
        "BM25 finds the four best help passages, and a summary of the traveller's trips is added: titles, dates and statuses, never names, emails or payment details. The model must answer from these and cite them; with no model available, the passages are shown as they are. A small text classifier sorts the question into a support topic and offers “Contact support” where it fits. The assistant never books, pays or cancels.",
    },
    {
      title: "When the airline cancels",
      call: "POST /api/v1/admin/operations/disruptions, then POST /api/v1/recovery/cases/{id}/accept",
      hops: ["Admin console", "Recovery", "PostgreSQL", "Traveller chooses", "Bookings"],
      detail:
        "An operator records the disruption. Recovery finds every affected item: unpaid holds are released, paid ones get a case with real options (another flight or room, a refund, or keeping a delayed flight), and the traveller is notified. When they choose, price and seats are checked again and only the affected item is replaced. The rest of the trip is untouched, and every change goes on the timeline.",
    },
    {
      title: "Meanwhile, the worker",
      call: "python -m app.worker, with no web traffic",
      hops: ["Worker", "Redis lock", "PostgreSQL"],
      detail:
        "A separate process runs jobs on timers: release unpaid holds every 30 seconds, re-check price alerts, retrain stay preferences, and once a day delete data past its retention date. Before each run it takes a Redis lock that expires just before the next run, so with several workers a job still runs once, and a crashed run never blocks the next. Holds are released with SKIP LOCKED, so two sweepers never touch the same booking.",
    },
    {
      title: "Watching it all",
      call: "GET /metrics, and traces over OpenTelemetry",
      hops: ["API and worker", "Prometheus", "Grafana", "Jaeger"],
      detail:
        "Every request is counted and timed for Prometheus, alongside business counters such as searches, holds, payments, refunds and expired holds; the worker reports each run and a heartbeat. Prometheus checks the alert rules, and Grafana draws the dashboards. With tracing on, each request's path, down to its SQL statements, goes to Jaeger: statement text only, never the values.",
    },
  ],
  tiers: [
    {
      name: "Browser",
      nodes: [
        { label: "Website", steps: [0, 1, 2, 3, 4, 5, 6, 7] },
        { label: "Admin console", steps: [8] },
      ],
    },
    {
      name: "Next.js server",
      nodes: [
        { label: "Page rendering", steps: [0] },
        { label: "/api proxy", steps: [1, 2, 3, 4, 5, 6, 7, 8] },
      ],
    },
    {
      name: "API (FastAPI)",
      nodes: [
        { label: "Request ID, limits, sign-in", steps: [1, 5, 6] },
        { label: "AI module", steps: [2, 7] },
        { label: "Search", steps: [3, 4] },
        { label: "Planner", steps: [4] },
        { label: "Bookings", steps: [5, 6, 8] },
        { label: "Recovery", steps: [8] },
      ],
    },
    {
      name: "Stores",
      nodes: [
        { label: "PostgreSQL", steps: [2, 3, 4, 5, 6, 7, 8, 9] },
        { label: "Redis", steps: [1, 2, 7, 9] },
      ],
    },
    {
      name: "Helpers",
      nodes: [
        { label: "LightGBM models", steps: [3, 4], tag: "Models" },
        { label: "Text classifier", steps: [7], tag: "Models" },
        { label: "BM25 help search", steps: [7] },
        { label: "Groq, Gemini, OpenRouter", steps: [2, 7], tag: "AI" },
        { label: "Card processor (simulated)", steps: [6] },
      ],
    },
    {
      name: "Alongside",
      nodes: [
        { label: "Worker", steps: [9] },
        { label: "Prometheus and Grafana", steps: [10] },
        { label: "Jaeger", steps: [10] },
      ],
    },
  ] satisfies Array<{ name: string; nodes: FlowNode[] }>,
  note: "Lit parts are the ones the current call touches. Redis, the AI providers and monitoring are optional: without them, TripMind still works.",
};

// ── 10 · Built with: each choice and the reason for it ───────────────────────────────────────

export const techStack: StackItem[] = [
  {
    area: "Web app",
    choice: "Next.js 16, React 19, TypeScript",
    why: "Pages are rendered on the server, so they open fast, and the built-in proxy puts the API on the same address, so sign-in can use secure httpOnly cookies.",
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
    why: "Caching, retries and loading states for every API call, wrapped once so pages never flicker while they load.",
    insteadOf: "Hand-written fetch calls in every component repeat the same mistakes.",
  },
  {
    area: "Motion",
    choice: "Lenis and CSS variables",
    why: "Smooth scrolling, with every animation worked out by CSS from one scroll value, so React does not redraw on each frame.",
    insteadOf: "Animating each element from JavaScript on every frame is slower.",
  },
  {
    area: "API",
    choice: "Python 3.12 and FastAPI",
    why: "One language for the API and the models. Requests are checked from type hints, and the API describes itself, which generates the website's types.",
    insteadOf: "Node.js would split the backend and the models across two languages; Django is heavier for a pure API.",
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
    why: "Transactions and conditional updates let exactly one buyer win the last seat, partial unique indexes allow one passenger per seat, and a failed schema change rolls back cleanly.",
    insteadOf: "MySQL has no partial indexes and commits schema changes implicitly; MongoDB suits loose documents better than tightly linked bookings, payments and seats.",
  },
  {
    area: "Shared state",
    choice: "Redis 7.4",
    why: "Fast shared memory for rate limits, the AI cache, provider cooldowns and job locks, so several copies of the API agree. It is optional: limits fail open and locks fail closed.",
    insteadOf: "Memory inside each server copy is not shared, and database tables would add load to the source of truth.",
  },
  {
    area: "Background jobs",
    choice: "One worker process",
    why: "Releases unpaid holds, re-prices price alerts, retrains preferences and applies retention, each job under a Redis lock so it never runs twice.",
    insteadOf: "Celery and a message broker add moving parts for four jobs.",
  },
  {
    area: "Models",
    choice: "LightGBM and scikit-learn",
    why: "Small models that run on a laptop CPU, saved as text or JSON so loading one can never run hidden code.",
    insteadOf: "Deep learning needs a GPU and far more data.",
  },
  {
    area: "Language AI",
    choice: "Groq, Gemini and OpenRouter",
    why: "Free hosted models behind one OpenAI-compatible client, tried in order with timeouts, cooldowns and a cache.",
    insteadOf: "A local model of useful size does not fit this laptop's 4 GB graphics card.",
  },
  {
    area: "Help search",
    choice: "BM25",
    why: "Finds the right help article with no model and no quota, so the assistant still answers with AI off.",
    insteadOf: "Embeddings and a vector database are a heavier setup for a small set of articles.",
  },
  {
    area: "Security",
    choice: "Argon2id, short-lived tokens in httpOnly cookies",
    why: "Memory-hard password hashing that resists cracking on graphics cards, and sessions that page scripts cannot read.",
    insteadOf: "bcrypt, and tokens kept in browser storage where any injected script can read them.",
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
    why: "The whole stack starts with one command on any machine.",
    insteadOf: "Kubernetes is more than one machine needs.",
  },
  {
    area: "Quality",
    choice: "pytest, Playwright, ruff, mypy, import-linter, GitHub Actions",
    why: "Tests on two databases, journeys in a real browser, type checks, and a rule that fails the build when code crosses its layers.",
  },
];

export const capabilityGroups: Group[] = [
  {
    name: "Booking, for real",
    items: ["Flight and stay search", "Itemised prices", "Holds and payments", "Changes and cancellations", "Seats, bags and meals", "Promo codes", "Add-on booking"],
    summary: "Search flights and stays, see every price line by line, hold, pay, then change or cancel a single item, with seats, bags, meals and promo codes.",
    status: "live",
  },
  {
    name: "The connected trip",
    items: ["Trip planner", "Journey Confidence Report", "What the trip is missing", "Plan with friends", "Fare calendar", "Explore by budget", "Saved stays and price alerts"],
    summary: "Ranked flight and stay packages with reasons, a trip that suggests its missing piece, group voting with budgets, and ways to find the cheapest day or where a budget can take you.",
    status: "live",
  },
  {
    name: "After booking",
    items: ["Disruption recovery", "Notifications", "Reviews", "Support requests", "Saved travellers", "Loyalty points", "Invoice"],
    summary: "When an airline cancels, the traveller chooses the fix. Alerts, reviews after the stay, support requests filed by topic, and points that follow refunds.",
    status: "live",
  },
  {
    name: "AI and models",
    items: ["Sentence search", "Ask TripMind", "Hotel ranker", "Fare estimator", "Personal recommendations", "Review sentiment", "Request classifier", "Similar stays", "Price anomaly check"],
    summary: "Two language features and seven small models, each with plain rules underneath, so switching any of them off changes nothing a traveller depends on.",
    status: "live",
  },
  {
    name: "Accounts, safety and privacy",
    items: ["Secure sessions", "Password reset and lockout", "Sign out everywhere", "Data export and deletion", "Audit trail", "Clear error codes"],
    summary: "Sessions that scripts cannot steal, protection against password guessing, a record of every sign-in, and travellers who can take their data or delete it.",
    status: "live",
  },
  {
    name: "Running it",
    items: ["Admin consoles", "Model status", "User management", "Monitoring dashboards", "Health checks", "Feature flags", "One-command start"],
    summary: "Admins handle disruptions, support, models and accounts; dashboards and alerts show what is happening; and every feature can be switched on or off.",
    status: "live",
  },
  {
    name: "The website",
    items: ["Home page", "This presentation", "Phone to large screen", "Motion switch"],
    summary: "A cinematic home page and this scroll-driven presentation, one design across every page, and a calmer layout for anyone who prefers less motion.",
    status: "live",
  },
];

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
    name: "AI has gone home",
    items: ["Provider down or busy"],
    summary: "The next provider is tried, then simple rules. Booking carries on as if nothing happened.",
    status: "live",
  },
];

// ── 12 · Proof (only measured results) ────────────────────────────────────────────────────────

export const proof = {
  measured: [
    { value: "20 → 1", label: "buyers racing for one seat on PostgreSQL (real threads): one booked, 19 told it sold out", measuredOn: "9 Nov 2026" },
    { value: "910 / 0", label: "synthetic requests from 8 virtual users in 46 s / server errors; search p95 0.47 s on a laptop in Docker", measuredOn: "7 Nov 2026" },
    { value: "100% / 100%", label: "precision / recall of the fare anomaly detector on 71,403 fares with injected price errors (3 seeds)", measuredOn: "7 Nov 2026" },
    { value: "212", label: "automated backend tests passing on both SQLite and PostgreSQL", measuredOn: "9 Nov 2026" },
  ],
  demoScript: [
    "Sign up, or sign in with one click as the demo traveller",
    "Book a flight on its own, then a hotel on its own",
    "Plan a connected trip and compare bundles",
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
