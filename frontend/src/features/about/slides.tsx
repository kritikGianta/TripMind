import { ArrowRight, Check, CircleDashed, Quote, X } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import * as about from "@/content/about";
import type { Capability, Status } from "@/content/about";
import { cn } from "@/lib/utils";

import type { DeckSlide } from "./deck";

// ── Building blocks ──────────────────────────────────────────────────────────────────────────

function SlideHeader({ index, eyebrow, title, lead }: { index: number; eyebrow: string; title: string; lead?: string }) {
  return (
    <header className="mb-8 grid gap-3">
      <p className="text-sm font-medium tracking-wide text-primary uppercase">
        {String(index).padStart(2, "0")} · {eyebrow}
      </p>
      <h2 className="max-w-4xl text-3xl font-semibold tracking-tight text-balance md:text-4xl">{title}</h2>
      {lead ? <p className="max-w-3xl text-lg text-muted-foreground text-pretty">{lead}</p> : null}
    </header>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  return status === "live" ? (
    <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">
      <Check /> Live
    </Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground">
      <CircleDashed /> Planned
    </Badge>
  );
}

function CapabilityList({ items, columns = 2 }: { items: Capability[]; columns?: 1 | 2 }) {
  return (
    <ul className={cn("grid gap-3", columns === 2 && "md:grid-cols-2")}>
      {items.map((item) => (
        <li key={item.name} className="flex items-start justify-between gap-4 rounded-lg border p-4">
          <div className="grid gap-1">
            <span className="font-medium">{item.name}</span>
            <span className="text-sm text-muted-foreground">{item.detail}</span>
          </div>
          <StatusBadge status={item.status} />
        </li>
      ))}
    </ul>
  );
}

function Panel({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-xl border bg-card p-5", className)}>
      <h3 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground uppercase">{title}</h3>
      {children}
    </div>
  );
}

// ── Slides, in presentation order ────────────────────────────────────────────────────────────

const referenceNumber = (id: string) => about.references.findIndex((r) => r.id === id) + 1;

export function buildSlides(): DeckSlide[] {
  let n = 0;
  const next = () => ++n;

  return [
    {
      id: "thought",
      title: "Opening thought",
      content: (
        <figure className="mx-auto grid max-w-4xl gap-8 text-center">
          <Quote className="mx-auto size-10 text-primary" aria-hidden />
          <blockquote className="text-4xl font-semibold tracking-tight text-balance md:text-6xl">
            {about.openingQuote.text}
          </blockquote>
          <figcaption className="text-muted-foreground">{about.openingQuote.attribution}</figcaption>
        </figure>
      ),
    },
    {
      id: "case-studies",
      title: "Case studies",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Case studies" title="What the research says about how people book travel" />
          <div className="grid gap-4 lg:grid-cols-2">
            {about.caseStudies.map((study) => (
              <article key={study.title} className="grid content-start gap-3 rounded-xl border bg-card p-5">
                <div>
                  <p className="text-xs text-muted-foreground">
                    {study.source} · {study.date} · [{referenceNumber(study.referenceId)}]
                  </p>
                  <h3 className="font-semibold">{study.title}</h3>
                  <p className="text-xs text-muted-foreground">{study.base}</p>
                </div>
                <dl className="grid gap-1.5">
                  {study.stats.map((stat) => (
                    <div key={stat.label} className="flex items-baseline gap-3">
                      <dt className="min-w-16 text-lg font-semibold text-primary tabular-nums">{stat.value}</dt>
                      <dd className="text-sm">{stat.label}</dd>
                    </div>
                  ))}
                </dl>
                {study.quote ? (
                  <blockquote className="border-l-2 border-primary/40 pl-3 text-sm italic text-muted-foreground">
                    “{study.quote}”
                  </blockquote>
                ) : null}
                <p className="flex gap-2 text-sm font-medium">
                  <ArrowRight className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                  {study.takeaway}
                </p>
              </article>
            ))}
          </div>
        </>
      ),
    },
    {
      id: "problem",
      title: "Problem statement",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Problem statement" title="Planning a trip is still a puzzle the traveller assembles by hand" />
          <Badge variant="outline" className="mb-4">{about.problemStatement.label}</Badge>
          <p className="mb-8 max-w-4xl text-lg text-pretty">{about.problemStatement.text}</p>
          <ol className="grid gap-3 md:grid-cols-5">
            {about.problemStatement.pains.map((pain, i) => (
              <li key={pain.title} className="rounded-lg border p-4">
                <span className="text-sm font-semibold text-primary">{i + 1}</span>
                <p className="font-medium">{pain.title}</p>
                <p className="text-sm text-muted-foreground">{pain.detail}</p>
              </li>
            ))}
          </ol>
        </>
      ),
    },
    {
      id: "title",
      title: "Project title",
      content: (
        <div className="grid gap-10">
          <p className="text-sm font-medium tracking-wide text-primary uppercase">
            {String(next()).padStart(2, "0")} · Project
          </p>
          <h2 className="-mt-6 text-6xl font-semibold tracking-tight md:text-8xl">
            <span className="text-primary">Trip</span>Mind
          </h2>
          <dl className="grid gap-6 md:grid-cols-2">
            {about.titleMeaning.parts.map((part) => (
              <div key={part.word} className="rounded-xl border p-6">
                <dt className="text-2xl font-semibold">{part.word}</dt>
                <dd className="mt-1 text-lg text-muted-foreground">{part.meaning}</dd>
              </div>
            ))}
          </dl>
        </div>
      ),
    },
    {
      id: "objectives",
      title: "Objectives",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Objectives" title="What TripMind must do" />
          <ol className="grid gap-3 md:grid-cols-2">
            {about.objectives.map((objective, i) => (
              <li key={objective} className="flex gap-4 rounded-lg border p-4">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  {i + 1}
                </span>
                <span>{objective}</span>
              </li>
            ))}
          </ol>
        </>
      ),
    },
    {
      id: "solution",
      title: "The solution",
      content: (
        <>
          <SlideHeader
            index={next()}
            eyebrow="The solution"
            title="Three ways to book, one platform underneath"
            lead="Each mode works on its own. All three share the same search, pricing, booking engine and My Trips."
          />
          <CapabilityList items={about.bookingModes} columns={1} />
        </>
      ),
    },
    {
      id: "difference",
      title: "How it differs",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="How it differs" title="Compared with a typical booking flow" />
          <div className="overflow-hidden rounded-xl border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/60">
                <tr>
                  <th scope="col" className="p-3 font-medium">Typical</th>
                  <th scope="col" className="p-3 font-medium">TripMind</th>
                  <th scope="col" className="p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {about.differentiators.map((row) => (
                  <tr key={row.tripmind} className="border-t">
                    <td className="p-3 text-muted-foreground">{row.typical}</td>
                    <td className="p-3 font-medium">{row.tripmind}</td>
                    <td className="p-3"><StatusBadge status={row.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ),
    },
    {
      id: "implementation",
      title: "Implementation and workflow",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Implementation and workflow" title="How it is built, and what is running today" />
          <div className="grid gap-4 lg:grid-cols-[2fr_3fr]">
            <div className="grid content-start gap-4">
              <Panel title="Architecture">
                <ol className="grid gap-2">
                  {about.architecture.layers.map((layer) => (
                    <li key={layer.name} className="rounded-md bg-muted/50 p-3 text-sm">
                      <span className="font-medium">{layer.name}</span>
                      <span className="block text-muted-foreground">{layer.detail}</span>
                    </li>
                  ))}
                </ol>
              </Panel>
              <Panel title="Customer workflow">
                <ol className="flex flex-wrap items-center gap-1.5 text-sm">
                  {about.architecture.workflow.map((step, i) => (
                    <li key={step} className="flex items-center gap-1.5">
                      <span className="rounded-md border px-2 py-1">{step}</span>
                      {i < about.architecture.workflow.length - 1 ? <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden /> : null}
                    </li>
                  ))}
                </ol>
              </Panel>
            </div>
            <Panel title="Build status">
              <ul className="grid gap-2">
                {about.capabilities.map((c) => (
                  <li key={c.name} className="flex items-center justify-between gap-3 text-sm">
                    <span>
                      <span className="font-medium">{c.name}</span>
                      <span className="hidden text-muted-foreground xl:inline"> · {c.detail}</span>
                    </span>
                    <StatusBadge status={c.status} />
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </>
      ),
    },
    {
      id: "data",
      title: "Data handling",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Data handling" title="Any supplied dataset, imported honestly" />
          <div className="mb-3"><StatusBadge status={about.dataPipeline.status} /></div>
          <ol className="mb-6 grid gap-2 md:grid-cols-7">
            {about.dataPipeline.steps.map((step, i) => (
              <li key={step.name} className={cn("rounded-lg border p-3", step.name === "Quarantine" && "border-amber-500/60 bg-amber-500/5")}>
                <span className="text-xs font-semibold text-primary">{i + 1}</span>
                <p className="text-sm font-medium">{step.name}</p>
                <p className="text-xs text-muted-foreground">{step.detail}</p>
              </li>
            ))}
          </ol>
          <ul className="grid gap-2">
            {about.dataPipeline.principles.map((p) => (
              <li key={p} className="flex gap-2"><Check className="mt-1 size-4 shrink-0 text-primary" aria-hidden />{p}</li>
            ))}
          </ul>
        </>
      ),
    },
    {
      id: "ai",
      title: "AI boundaries",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="AI boundaries" title="AI suggests. The traveller decides." />
          <div className="mb-3"><StatusBadge status={about.aiBoundaries.status} /></div>
          <div className="grid gap-4 md:grid-cols-2">
            <Panel title="AI may">
              <ul className="grid gap-2">
                {about.aiBoundaries.allowed.map((item) => (
                  <li key={item} className="flex gap-2 text-sm"><Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />{item}</li>
                ))}
              </ul>
            </Panel>
            <Panel title="AI may not">
              <ul className="grid gap-2">
                {about.aiBoundaries.notAllowed.map((item) => (
                  <li key={item} className="flex gap-2 text-sm"><X className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />{item}</li>
                ))}
              </ul>
            </Panel>
          </div>
          <p className="mt-4 text-muted-foreground">{about.aiBoundaries.fallback}</p>
        </>
      ),
    },
    {
      id: "edge-cases",
      title: "Edge cases",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Edge cases being solved" title="What happens when things go wrong" />
          <CapabilityList items={about.edgeCases} />
        </>
      ),
    },
    {
      id: "proof",
      title: "Live demo and proof",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Live demo and proof" title="Measured, not claimed" />
          <div className="grid gap-4 md:grid-cols-2">
            <Panel title="Measured so far">
              <ul className="grid gap-4">
                {about.proof.measured.map((m) => (
                  <li key={m.label}>
                    <span className="text-4xl font-semibold text-primary tabular-nums">{m.value}</span>
                    <p className="text-sm">{m.label}</p>
                    <p className="text-xs text-muted-foreground">Measured {m.measuredOn}</p>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Demo script">
              <ol className="grid list-decimal gap-2 pl-5 text-sm">
                {about.proof.demoScript.map((step) => <li key={step}>{step}</li>)}
              </ol>
            </Panel>
          </div>
        </>
      ),
    },
    {
      id: "business",
      title: "Business model",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Business model" title="Who pays, and for what" lead={about.businessModel.positioning} />
          <div className="mb-4 grid gap-3 md:grid-cols-3">
            {about.businessModel.streams.map((s) => (
              <div key={s.name} className="rounded-lg border p-4">
                <p className="font-medium">{s.name}</p>
                <p className="text-sm text-muted-foreground">Payer: {s.payer}</p>
                <p className="text-sm">{s.value}</p>
              </div>
            ))}
          </div>
          <Panel title="Unit economics">
            <p className="font-mono text-sm">{about.businessModel.unitEconomics}</p>
            <p className="mt-3 text-sm text-muted-foreground">To validate: {about.businessModel.validate.join(" · ")}</p>
          </Panel>
          <p className="mt-4 text-sm text-muted-foreground">{about.businessModel.note}</p>
        </>
      ),
    },
    {
      id: "limits",
      title: "Limits and what is next",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="Limits and what is next" title="What this prototype is, and is not" />
          <div className="grid gap-4 md:grid-cols-2">
            <Panel title="Honest limits today">
              <ul className="grid list-disc gap-2 pl-5">{about.limits.today.map((l) => <li key={l}>{l}</li>)}</ul>
            </Panel>
            <Panel title="Path to production">
              <ul className="grid list-disc gap-2 pl-5">{about.limits.next.map((l) => <li key={l}>{l}</li>)}</ul>
            </Panel>
          </div>
        </>
      ),
    },
    {
      id: "closing",
      title: "The thought, explained",
      content: (
        <div className="mx-auto grid max-w-5xl gap-8">
          <blockquote className="text-center text-3xl font-semibold tracking-tight text-balance md:text-5xl">
            “{about.closing.quote}”
          </blockquote>
          <ul className="grid gap-3 md:grid-cols-3">
            {about.closing.pieces.map((p) => (
              <li key={p.piece} className="rounded-xl border p-5">
                <p className="text-sm font-medium text-muted-foreground line-through decoration-primary/60">{p.piece}</p>
                <p className="mt-2 font-medium">{p.answer}</p>
              </li>
            ))}
          </ul>
          <p className="text-center text-xl text-primary">{about.closing.line}</p>
        </div>
      ),
    },
    {
      id: "references",
      title: "References",
      content: (
        <>
          <SlideHeader index={next()} eyebrow="References" title="Sources" lead="Each figure in this deck was checked against its source on the date shown." />
          <ol className="grid gap-3">
            {about.references.map((r, i) => (
              <li key={r.id} className="text-sm">
                <span className="font-medium">[{i + 1}]</span> {r.citation}{" "}
                <a href={r.url} target="_blank" rel="noreferrer noopener" className="break-all text-primary underline-offset-4 hover:underline">
                  {r.url}
                </a>{" "}
                <span className="text-muted-foreground">(checked {r.checkedOn})</span>
              </li>
            ))}
          </ol>
        </>
      ),
    },
  ];
}
