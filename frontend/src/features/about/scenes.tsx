"use client";

import { Check, CircleDashed, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { type CSSProperties, type ReactNode } from "react";

import { siteConfig } from "@/config/site";
import * as about from "@/content/about";
import type { ArtName, Group, Status } from "@/content/about";
import { useScrollProgress } from "@/features/home/motion";

type Style = CSSProperties & Record<`--${string}`, string | number>;

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];

function sceneOf(id: (typeof about.scenes)[number]["id"]) {
  const scene = about.scenes.find((item) => item.id === id)!;
  return scene as { id: string; title: string; heading?: string; lead?: string };
}

/** Numbered like the original deck: the opening and closing thoughts carry no number. */
function Eyebrow({ id }: { id: (typeof about.scenes)[number]["id"] }) {
  const numbered = about.scenes.filter((scene) => scene.id !== "thought" && scene.id !== "closing");
  const number = numbered.findIndex((scene) => scene.id === id) + 1;
  return (
    <p className="ab-eyebrow">
      {String(number).padStart(2, "0")} · {sceneOf(id).title}
    </p>
  );
}

function Heading({ id, className }: { id: (typeof about.scenes)[number]["id"]; className?: string }) {
  return <h2 className={`ab-display ab-h2 ${className ?? ""}`}>{sceneOf(id).heading}</h2>;
}

export function StatusMark({ status }: { status: Status }) {
  return (
    <span className="ab-status" data-status={status}>
      {status === "live" ? <Check aria-hidden /> : <CircleDashed aria-hidden />}
      {status === "live" ? "Live" : "Planned"}
    </span>
  );
}

function Art({ name, sizes, className, style, priority }: { name: ArtName; sizes: string; className?: string; style?: Style; priority?: boolean }) {
  const art = about.artwork[name];
  return (
    <figure className={`ab-art ${className ?? ""}`} style={style}>
      <Image src={art.src} alt={`${art.title}, ${art.artist}, ${art.year}`} fill sizes={sizes} priority={priority} />
    </figure>
  );
}

/** Words that light up one at a time as the scene's `--p` advances. */
function Words({ text, from = 0, span = 0.75 }: { text: string; from?: number; span?: number }) {
  const words = text.split(" ");
  return (
    <>
      {words.map((word, index) => (
        <span key={`${word}-${index}`} className="ab-word" style={{ "--w": from + (index / words.length) * span } as Style}>
          {word}{" "}
        </span>
      ))}
    </>
  );
}

function Hero() {
  const ref = useScrollProgress<HTMLElement>("pass");
  const [first, ...rest] = about.openingQuote.text.split(". ");
  return (
    <section ref={ref} id="thought" data-scene className="ab-hero" aria-label={sceneOf("thought").title}>
      <div className="ab-hero__cloud">
        <Image src="/about/cloud.webp" alt="" fill sizes="(min-width: 900px) 110vw, 180vw" priority />
      </div>
      <figure className="ab-hero__text">
        <blockquote className="ab-display ab-hero__quote">
          {first}. <em>{rest.join(". ")}</em>
        </blockquote>
        <figcaption>{about.openingQuote.attribution}</figcaption>
      </figure>
      <p className="ab-hero__hint">Scroll, or press → to begin</p>
    </section>
  );
}

const STUDY_ART: ArtName[][] = [
  ["temeraire", "railway"],
  ["map", "voyage"],
  ["wanderer", "sierra"],
  ["sierra", "wave"],
];

function CaseStudies() {
  const ref = useScrollProgress<HTMLElement>("pin");
  const count = about.caseStudies.length + 1;
  const referenceNumber = (id: string) => about.references.findIndex((reference) => reference.id === id) + 1;
  const place = (index: number): Style => ({ "--c": index / (count - 1) });
  return (
    <section ref={ref} id="case-studies" data-scene data-stops={count} className="ab-h" style={{ "--n": count } as Style} aria-label={sceneOf("case-studies").title}>
      <div className="ab-h__stage">
        <div className="ab-h__track">
          <article className="ab-panel ab-panel--intro" style={place(0)}>
            <div className="ab-panel__text">
              <Eyebrow id="case-studies" />
              <Heading id="case-studies" className="ab-h2--wide" />
            </div>
            <div className="ab-panel__art">
              <Art name="wanderer" sizes="30vw" className="ab-art--tall" style={{ "--d": -0.5 }} />
              <Art name="wave" sizes="24vw" className="ab-art--low" style={{ "--d": 0.5 }} />
            </div>
          </article>
          {about.caseStudies.map((study, index) => (
            <article key={study.title} className="ab-panel" style={place(index + 1)}>
              <div className="ab-panel__text">
                <p className="ab-small">
                  {study.source} · {study.date} · [{referenceNumber(study.referenceId)}]
                </p>
                <h3 className="ab-display ab-h3">{study.title}</h3>
                <p className="ab-small ab-soft">{study.base}</p>
                <dl className="ab-stats">
                  {study.stats.map((stat) => (
                    <div key={stat.label}>
                      <dt>{stat.value}</dt>
                      <dd>{stat.label}</dd>
                    </div>
                  ))}
                </dl>
                {study.quote ? <blockquote className="ab-quote">“{study.quote}”</blockquote> : null}
                <p className="ab-takeaway">→ {study.takeaway}</p>
              </div>
              <div className="ab-panel__art">
                <Art name={STUDY_ART[index][0]} sizes="30vw" className="ab-art--tall" style={{ "--d": -0.5 }} />
                <Art name={STUDY_ART[index][1]} sizes="24vw" className="ab-art--low" style={{ "--d": 0.5 }} />
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

const PAIN_ART: ArtName[] = ["map", "voyage", "temeraire", "wanderer", "wave"];

function Problem() {
  const ref = useScrollProgress<HTMLElement>("pin");
  return (
    <div id="problem" data-scene data-stops={1} aria-label={sceneOf("problem").title} role="region">
      <section ref={ref} className="ab-read">
        <div className="ab-read__stage">
          <Eyebrow id="problem" />
          <Heading id="problem" />
          <p className="ab-chip">{about.problemStatement.label}</p>
          <p className="ab-read__text">
            <Words text={about.problemStatement.text} from={0.08} />
          </p>
        </div>
      </section>
      <ol className="ab-rows">
        {about.problemStatement.pains.map((pain, index) => (
          <li key={pain.title} className="ab-row" data-reveal data-art={about.artwork[PAIN_ART[index]].src}>
            <span className="ab-row__mark">{ROMAN[index]}</span>
            <span className="ab-display ab-row__title">{pain.title}</span>
            <span className="ab-row__detail">{pain.detail}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Letters({ word, from }: { word: string; from: number }) {
  return (
    <>
      {word.split("").map((letter, index) => (
        <span key={`${letter}-${index}`} className="ab-letter" style={{ "--l": from + index } as Style}>
          {letter}
        </span>
      ))}
    </>
  );
}

function ProjectTitle() {
  const ref = useScrollProgress<HTMLElement>("pin");
  const [trip, mind] = about.titleMeaning.parts;
  return (
    <section ref={ref} id="title" data-scene className="ab-name" aria-label={sceneOf("title").title}>
      <div className="ab-name__stage">
        <div className="ab-name__sky">
          <Image src="/about/cloud-copper.webp" alt="" fill sizes="100vw" />
        </div>
        <Eyebrow id="title" />
        <h2 className="ab-display ab-name__word">
          <Letters word={trip.word} from={0} />
          <Letters word={mind.word} from={trip.word.length} />
        </h2>
        <dl className="ab-name__parts">
          {about.titleMeaning.parts.map((part) => (
            <div key={part.word}>
              <dt className="ab-display">{part.word}</dt>
              <dd>{part.meaning}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

const OBJECTIVE_ART: ArtName[] = ["temeraire", "sierra", "voyage", "map", "railway", "wave", "wanderer", "temeraire"];

function Objectives() {
  return (
    <section id="objectives" data-scene className="ab-plain" aria-label={sceneOf("objectives").title}>
      <Eyebrow id="objectives" />
      <Heading id="objectives" />
      <ol className="ab-rows ab-rows--tight">
        {about.objectives.map((objective, index) => (
          <li key={objective} className="ab-row ab-row--line" data-reveal data-art={about.artwork[OBJECTIVE_ART[index]].src}>
            <span className="ab-row__mark">{ROMAN[index]}</span>
            <span className="ab-row__wide">{objective}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Solution() {
  const ref = useScrollProgress<HTMLElement>("pin");
  const scene = sceneOf("solution");
  return (
    <section ref={ref} id="solution" data-scene data-stops={2} className="ab-frame" aria-label={scene.title}>
      <div className="ab-frame__stage">
        <div className="ab-frame__head">
          <Eyebrow id="solution" />
          <Heading id="solution" />
          <p className="ab-lead">{scene.lead}</p>
        </div>
        <div className="ab-frame__picture">
          <Art name="voyage" sizes="100vw" />
        </div>
        <ul className="ab-modes">
          {about.bookingModes.map((mode) => (
            <li key={mode.name}>
              <div className="ab-modes__top">
                <h3 className="ab-display">{mode.name}</h3>
                <StatusMark status={mode.status} />
              </div>
              <p>{mode.detail}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Difference() {
  return (
    <section id="difference" data-scene className="ab-plain" aria-label={sceneOf("difference").title}>
      <Eyebrow id="difference" />
      <Heading id="difference" />
      <table className="ab-compare">
        <thead>
          <tr>
            <th scope="col">Typical</th>
            <th scope="col">TripMind</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {about.differentiators.map((row) => (
            <tr key={row.tripmind} data-reveal>
              <td data-label="Typical">
                <span className="ab-compare__old">{row.typical}</span>
              </td>
              <td data-label="TripMind" className="ab-compare__new">{row.tripmind}</td>
              <td data-label="Status">
                <StatusMark status={row.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/**
 * How it works, as a diagram that runs while it is pinned: each step's caption takes its turn on
 * the left, and the parts of TripMind doing that step light up on the right.
 */
function HowItWorks() {
  const ref = useScrollProgress<HTMLElement>("pin");
  const scene = sceneOf("workflow");
  const { steps, lanes, note } = about.workflow;
  return (
    <div id="workflow" data-scene data-stops={steps.length} role="region" aria-label={scene.title}>
      <section ref={ref} className="ab-how" style={{ "--n": steps.length - 1 } as Style}>
        <div className="ab-how__stage">
          <div className="ab-how__head">
            <Eyebrow id="workflow" />
            <Heading id="workflow" />
            <p className="ab-lead">{scene.lead}</p>
          </div>
          <div className="ab-how__body">
            <ol className="ab-how__steps">
              {steps.map((step, index) => (
                <li key={step.title} style={{ "--i": index } as Style}>
                  <span className="ab-row__mark">{String(index + 1).padStart(2, "0")}</span>
                  <h3 className="ab-display">{step.title}</h3>
                  <p>{step.detail}</p>
                </li>
              ))}
            </ol>
            <div className="ab-how__map">
              {lanes.map((lane) => (
                <div key={lane.name} className="ab-how__lane">
                  <p className="ab-how__lane-name">{lane.name}</p>
                  <ul>
                    {lane.nodes.map((node: about.WorkflowNode) => (
                      <li key={node.label} className="ab-how__node" style={{ "--s": node.step } as Style}>
                        {node.label}
                        {node.tag ? <span className="ab-how__tag">{node.tag}</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              <p className="ab-small ab-soft">{note}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

/**
 * Under the hood: the real API calls, one at a time while the scene is pinned. Each caption names
 * the call and reveals its hops in order; on the right, every part that call passes through glows.
 * A part can serve several calls, so each step gets a glow value (--k0, --k1, …) worked out from
 * the scroll position, and a part takes the brightest of the steps it belongs to.
 */
function UnderTheHood() {
  const ref = useScrollProgress<HTMLElement>("pin");
  const scene = sceneOf("under-the-hood");
  const { calls, tiers, note } = about.requestFlow;
  const last = calls.length - 1;
  const glow: Style = { "--n": last };
  calls.forEach((_, index) => {
    glow[`--k${index}`] =
      `clamp(0, calc(1.15 - max(var(--p, 0) * ${last} - ${index}, ${index} - var(--p, 0) * ${last}) * 2.4), 1)`;
  });
  return (
    <div id="under-the-hood" data-scene data-stops={calls.length} role="region" aria-label={scene.title}>
      <section ref={ref} className="ab-how ab-hood" style={glow}>
        <div className="ab-how__stage">
          <div className="ab-how__head">
            <Eyebrow id="under-the-hood" />
            <Heading id="under-the-hood" />
            <p className="ab-lead">{scene.lead}</p>
          </div>
          <div className="ab-how__body">
            <ol className="ab-how__steps">
              {calls.map((call, index) => (
                <li key={call.title} style={{ "--i": index } as Style}>
                  <span className="ab-row__mark">{String(index + 1).padStart(2, "0")}</span>
                  <h3 className="ab-display">{call.title}</h3>
                  <code className="ab-hood__call">{call.call}</code>
                  <ol className="ab-hood__hops" aria-label="Hops">
                    {call.hops.map((hop, hopIndex) => (
                      <li key={hop} style={{ "--j": hopIndex } as Style}>
                        {hop}
                      </li>
                    ))}
                  </ol>
                  <p>{call.detail}</p>
                </li>
              ))}
            </ol>
            <div className="ab-how__map ab-hood__map">
              {tiers.map((tier) => (
                <div key={tier.name} className="ab-hood__tier">
                  <p className="ab-how__lane-name">{tier.name}</p>
                  <ul>
                    {tier.nodes.map((node: about.FlowNode) => (
                      <li
                        key={node.label}
                        className="ab-hood__node"
                        style={{ "--hot": `max(${node.steps.map((s) => `var(--k${s})`).join(", ")})` } as Style}
                      >
                        {node.label}
                        {node.tag ? <span className="ab-how__tag">{node.tag}</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              <p className="ab-small ab-soft">{note}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

/** Several related capabilities or cases as one card: their names, then one summary. */
function GroupCard({ group, index }: { group: Group; index: number }) {
  return (
    <li className="ab-group" data-reveal style={{ "--i": index % 2 } as Style}>
      <div className="ab-group__top">
        <h4 className="ab-display">{group.name}</h4>
        <StatusMark status={group.status} />
      </div>
      <ul className="ab-group__items">
        {group.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="ab-group__summary">{group.summary}</p>
    </li>
  );
}

function Implementation() {
  const groups = about.capabilityGroups;
  const live = groups.filter((group) => group.status === "live").length;
  const features = groups.reduce((sum, group) => sum + group.items.length, 0);
  return (
    <section id="implementation" data-scene className="ab-plain" aria-label={sceneOf("implementation").title}>
      <Eyebrow id="implementation" />
      <Heading id="implementation" />

      <h3 className="ab-label ab-stack__label">Tech stack</h3>
      <ul className="ab-stack">
        {about.techStack.map((item, index) => (
          <li key={item.choice} data-reveal style={{ "--i": index % 2 } as Style}>
            <p className="ab-stack__area">{item.area}</p>
            <p className="ab-display ab-stack__choice">{item.choice}</p>
            <p>{item.why}</p>
            {item.insteadOf ? (
              <p className="ab-stack__over">
                <span>Why not the alternatives?</span> {item.insteadOf}
              </p>
            ) : null}
          </li>
        ))}
      </ul>

      <div className="ab-groups__head">
        <h3 className="ab-label">Build status</h3>
        <p className="ab-small ab-soft">
          {features} features in {groups.length} groups · {live} of {groups.length} groups live
        </p>
      </div>
      <ul className="ab-groups">
        {groups.map((group, index) => (
          <GroupCard key={group.name} group={group} index={index} />
        ))}
      </ul>
    </section>
  );
}

function AiBoundaries() {
  const ref = useScrollProgress<HTMLElement>("pass");
  const { allowed, notAllowed, fallback, status } = about.aiBoundaries;
  return (
    <section ref={ref} id="ai" data-scene className="ab-split" aria-label={sceneOf("ai").title}>
      <div className="ab-split__sky">
        <Art name="sierra" sizes="100vw" />
      </div>
      <div className="ab-split__inner">
        <Eyebrow id="ai" />
        <Heading id="ai" />
        <StatusMark status={status} />
        <div className="ab-split__panels">
          <div className="ab-split__panel ab-split__panel--may">
            <h3 className="ab-display">Every package must</h3>
            <ul>
              {allowed.map((item) => (
                <li key={item}>
                  <Check aria-hidden />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="ab-split__panel ab-split__panel--not">
            <h3 className="ab-display">TripMind never</h3>
            <ul>
              {notAllowed.map((item) => (
                <li key={item}>
                  <X aria-hidden />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="ab-lead">{fallback}</p>
      </div>
    </section>
  );
}

function EdgeCases() {
  const ref = useScrollProgress<HTMLElement>("pass");
  return (
    <section ref={ref} id="edge-cases" data-scene className="ab-edge" aria-label={sceneOf("edge-cases").title}>
      <div className="ab-edge__art">
        <Art name="wave" sizes="42vw" />
      </div>
      <div className="ab-edge__list">
        <Eyebrow id="edge-cases" />
        <Heading id="edge-cases" />
        <p className="ab-lead">
          {about.edgeCaseGroups.reduce((sum, group) => sum + group.items.length, 0)} ways a trip can go wrong, in{" "}
          {about.edgeCaseGroups.length} families.
        </p>
        <ul className="ab-groups ab-groups--single">
          {about.edgeCaseGroups.map((group, index) => (
            <GroupCard key={group.name} group={group} index={index} />
          ))}
        </ul>
      </div>
    </section>
  );
}

function Proof() {
  return (
    <section id="proof" data-scene className="ab-plain ab-proof" aria-label={sceneOf("proof").title}>
      <div>
        <Eyebrow id="proof" />
        <Heading id="proof" />
        <h3 className="ab-label">Measured so far</h3>
        <ul className="ab-proof__list">
          {about.proof.measured.map((item) => (
            <li key={item.label} data-reveal>
              <p className="ab-display ab-proof__value">{item.value}</p>
              <p>{item.label}</p>
              <p className="ab-small ab-soft">Measured {item.measuredOn}</p>
            </li>
          ))}
        </ul>
      </div>
      <aside className="ab-proof__demo">
        <h3 className="ab-label">Demo script</h3>
        <ol>
          {about.proof.demoScript.map((item, index) => (
            <li key={item}>
              <span className="ab-row__mark">{ROMAN[index]}</span>
              {item}
            </li>
          ))}
        </ol>
      </aside>
    </section>
  );
}

function Business() {
  const { positioning, streams, unitEconomics, validate, note } = about.businessModel;
  return (
    <section id="business" data-scene className="ab-plain ab-business" aria-label={sceneOf("business").title}>
      <Eyebrow id="business" />
      <Heading id="business" />
      <p className="ab-lead">{positioning}</p>
      <div className="ab-streams">
        {streams.map((stream, index) => (
          <article key={stream.name} data-reveal style={{ "--i": index } as Style}>
            <span className="ab-row__mark">{ROMAN[index]}</span>
            <h3 className="ab-display">{stream.name}</h3>
            <p className="ab-soft">Payer: {stream.payer}</p>
            <p>{stream.value}</p>
          </article>
        ))}
      </div>
      <div className="ab-formula" data-reveal>
        <h3 className="ab-label">Unit economics</h3>
        <p className="ab-formula__text">{unitEconomics}</p>
        <p className="ab-soft">To validate: {validate.join(" · ")}</p>
      </div>
      <p className="ab-small ab-soft">{note}</p>
    </section>
  );
}

function Limits() {
  const groups: Array<{ title: string; items: string[] }> = [
    { title: "Honest limits today", items: about.limits.today },
    { title: "Path to production", items: about.limits.next },
  ];
  return (
    <section id="limits" data-scene className="ab-limits" aria-label={sceneOf("limits").title}>
      <div className="ab-limits__sky">
        <Art name="railway" sizes="100vw" />
      </div>
      <div className="ab-limits__inner">
        <Eyebrow id="limits" />
        <Heading id="limits" />
        <div className="ab-limits__columns">
          {groups.map((group) => (
            <div key={group.title} data-reveal>
              <h3 className="ab-label">{group.title}</h3>
              <ul>
                {group.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/** The opening thought in fragments: scroll draws the pieces into one sentence. */
function Closing() {
  const ref = useScrollProgress<HTMLElement>("pin");
  const words = `“${about.closing.quote}”`.split(" ");
  return (
    <section ref={ref} id="closing" data-scene data-stops={2} className="ab-close" aria-label={sceneOf("closing").title}>
      <div className="ab-close__stage">
        <div className="ab-close__sky">
          <Image src="/about/cloud-copper.webp" alt="" fill sizes="100vw" />
        </div>
        <blockquote className="ab-display ab-close__quote">
          {words.map((word, index) => (
            <span
              key={`${word}-${index}`}
              className="ab-piece"
              style={{
                "--sx": `${((index * 67) % 100) - 50}vw`,
                "--sy": `${((index * 41) % 70) - 35}svh`,
                "--sr": `${((index * 53) % 60) - 30}deg`,
              } as Style}
            >
              {word}{" "}
            </span>
          ))}
        </blockquote>
        <ul className="ab-close__pieces">
          {about.closing.pieces.map((piece) => (
            <li key={piece.piece}>
              <p className="ab-close__old">{piece.piece}</p>
              <p>{piece.answer}</p>
            </li>
          ))}
        </ul>
        <p className="ab-display ab-close__line">{about.closing.line}</p>
      </div>
    </section>
  );
}

function ListSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="ab-refs__group">
      <h3 className="ab-label">{title}</h3>
      {children}
    </div>
  );
}

function References() {
  const scene = sceneOf("references");
  return (
    <section id="references" data-scene className="ab-plain ab-refs" aria-label={scene.title}>
      <Eyebrow id="references" />
      <Heading id="references" />
      <p className="ab-lead">{scene.lead}</p>
      <ListSection title="Figures">
        <ol>
          {about.references.map((reference, index) => (
            <li key={reference.id}>
              <span className="ab-row__mark">[{index + 1}]</span>
              <span>
                {reference.citation}{" "}
                <a href={reference.url} target="_blank" rel="noreferrer noopener" data-cursor="Open">
                  {reference.url}
                </a>{" "}
                <span className="ab-soft">(checked {reference.checkedOn})</span>
              </span>
            </li>
          ))}
        </ol>
      </ListSection>
    </section>
  );
}

function Footer() {
  return (
    <footer className="ab-foot">
      <div className="ab-foot__sky">
        <Image src="/about/cloud-copper.webp" alt="" fill sizes="100vw" />
      </div>
      <p className="ab-display ab-foot__word">{siteConfig.name}</p>
      <p className="ab-small">© {siteConfig.name}. {siteConfig.disclaimer}</p>
      <nav aria-label="Footer">
        <Link href="/">Home</Link>
        <Link href="/flights">Flights</Link>
        <Link href="/stays">Stays</Link>
        <Link href="/plan">Plan a trip</Link>
      </nav>
    </footer>
  );
}

export function Scenes() {
  return (
    <div className="ab-main">
      <Hero />
      <CaseStudies />
      <Problem />
      <ProjectTitle />
      <Objectives />
      <Solution />
      <Difference />
      <HowItWorks />
      <UnderTheHood />
      <Implementation />
      <AiBoundaries />
      <EdgeCases />
      <Proof />
      <Business />
      <Limits />
      <Closing />
      <References />
      <Footer />
    </div>
  );
}
