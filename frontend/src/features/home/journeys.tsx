"use client";

import { useQuery } from "@/lib/api/use-query";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { homeCopy } from "@/content/home";
import { toQuery, useDataset } from "@/features/search/api";
import { addDays, formatMoney, todayIso } from "@/features/search/format";
import { useMotionChoice } from "@/features/motion/use-motion";
import { apiFetch, type Schemas } from "@/lib/api/client";

import { Media, Rise, Scribble, useHome } from "./media";
import { scrollToSection, useScrollProgress } from "./motion";

const WAY_SECONDS = 4.2;

export function Ways() {
  const { heading, items } = homeCopy.ways;
  const [active, setActive] = useState(0);
  const ref = useScrollProgress<HTMLElement>("pass");
  const motion = useMotionChoice();
  const held = useRef(false);

  // The strip moves on by itself while it is on screen, until someone points at it.
  useEffect(() => {
    const section = ref.current;
    if (motion !== "full" || !section) return;
    let visible = false;
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
      },
      { threshold: 0.4 },
    );
    observer.observe(section);
    const timer = window.setInterval(() => {
      if (visible && !held.current && !document.hidden && window.matchMedia("(min-width: 1024px)").matches) {
        setActive((current) => (current + 1) % items.length);
      }
    }, WAY_SECONDS * 1000);
    return () => {
      observer.disconnect();
      window.clearInterval(timer);
    };
  }, [motion, items.length, ref]);

  return (
    <section ref={ref} className="tm-lines tm-ways" style={{ "--way": `${WAY_SECONDS}s` } as React.CSSProperties}>
      <div className="tm-ways__head">
        <h2 className="tm-serif-h tm-serif-h--lg" data-reveal="rise">
          <Rise text={heading} />
        </h2>
        <Scribble />
      </div>
      <div
        className="tm-ways__rail"
        onPointerEnter={() => {
          held.current = true;
        }}
        onPointerLeave={() => {
          held.current = false;
        }}
      >
        {items.map((way, index) => (
          <Link
            key={way.slot}
            href={way.href}
            className="tm-way"
            data-active={index === active}
            data-cursor={way.cta}
            style={{ "--i": index } as React.CSSProperties}
            onPointerEnter={() => setActive(index)}
            onFocus={() => setActive(index)}
            onClick={(event) => {
              if (way.href.startsWith("#")) {
                event.preventDefault();
                scrollToSection(way.href);
              }
            }}
          >
            <Media slot={way.slot} sizes="(max-width: 1023px) 100vw, 60vw" className="tm-way__media" />
            <div className="tm-way__shade" />
            <span className="tm-way__bar" aria-hidden />
            <div className="tm-way__body">
              <h3 className="tm-way__title">
                {way.title[0]}
                <br />
                {way.title[1]}
              </h3>
              <div className="tm-way__foot">
                <p className="tm-way__meta">
                  <span>{way.tag}</span>
                  <span>{way.meta}</span>
                </p>
                <p className="tm-way__text">{way.text}</p>
                <span className="tm-way__cta">
                  {way.cta} <ArrowRight className="size-3.5" aria-hidden />
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function Confidence() {
  const { label, text, checks } = homeCopy.confidence;
  return (
    <section className="tm-lines tm-confidence">
      <span className="tm-confidence__mark" aria-hidden>
        “
      </span>
      <p className="tm-italic tm-confidence__text" data-reveal>
        {text}
      </p>
      <h2 className="tm-label mt-8" data-reveal>
        {label}
      </h2>
      <dl className="tm-confidence__checks">
        {checks.map((check, index) => (
          <div key={check.name} data-reveal style={{ "--i": index + 1 } as React.CSSProperties}>
            <dt className="tm-italic">{check.name}</dt>
            <dd>{check.text}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

type Explore = Schemas["ExploreOut"];

/** Real prices from the search API. If it is unavailable the cards simply show no price. */
function useLivePrices() {
  const { origin, nights, adults } = homeCopy.destinations;
  const { data: dataset } = useDataset();
  // Three weeks out, inside the dataset's window. Only computed in the browser, once data has arrived.
  let depart = "";
  if (dataset) {
    const soonest = addDays(todayIso(), 21);
    const first = dataset.travel_window?.first_departure;
    depart = first && first > soonest ? first : soonest;
  }
  return useQuery({
    queryKey: ["home", "explore", origin.code, depart],
    enabled: Boolean(depart),
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: () =>
      apiFetch<Explore>(`/explore?${toQuery({ origin: origin.code, departure_date: depart, nights, adults })}`),
  });
}

export function Destinations() {
  const { heading, label, text, items, origin, adults } = homeCopy.destinations;
  const ref = useScrollProgress<HTMLElement>("pin", (p, el) => {
    const move = Math.min(1, Math.max(0, (p - 0.2) / 0.76));
    el.querySelectorAll<HTMLElement>(".tm-dest__card").forEach((card, index) => {
      const away = index - move * (items.length - 1);
      card.style.setProperty("--d", Math.min(1.7, Math.max(-1.7, away)).toFixed(3));
    });
  });
  const { data } = useLivePrices();
  const live = new Map(data?.options.map((option) => [option.city, option]));

  return (
    <section ref={ref} className="tm-dest" aria-label={heading} style={{ "--n": items.length } as React.CSSProperties}>
      <div className="tm-dest__stage">
        <Media slot="dest-opening" className="tm-dest__opening" />
        <div className="tm-dest__intro">
          <h2 className="tm-serif-h tm-serif-h--xl" data-reveal="rise">
            <Rise text={heading} />
          </h2>
          <div className="tm-dest__note">
            <p className="tm-label">{label}</p>
            <p>{text}</p>
          </div>
        </div>
        <Media slot="dest-backdrop" className="tm-dest__backdrop" />
        <div className="tm-dest__track">
          {items.map((item) => {
            const option = live.get(item.city);
            const href = option
              ? `/plan?${toQuery({
                  origin: origin.code,
                  originLabel: origin.label,
                  dest: option.city_id,
                  destLabel: option.city,
                  depart: data?.departure_date,
                  return: data?.return_date,
                  adults,
                })}`
              : "/plan";
            return (
              <Link key={item.slot} href={href} className="tm-dest__card" data-cursor="Plan this">
                <Media slot={item.slot} sizes="(max-width: 767px) 80vw, 34rem" className="tm-dest__card-media" />
                <div className="tm-dest__card-shade" />
                <div className="tm-dest__card-top">
                  <h3 className="tm-serif-h">{item.city}</h3>
                  <p>{item.text}</p>
                </div>
                <div className="tm-dest__card-foot">
                  {option ? (
                    <p className="tm-dest__price">
                      {formatMoney(option.total)} <span>for {adults}, flights and stay</span>
                    </p>
                  ) : null}
                  <p className="tm-dest__coords">[ {item.coords} ]</p>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function RouteCode() {
  const { code, from, to, heading, text } = homeCopy.route;
  const ref = useScrollProgress<HTMLElement>("pin");
  return (
    <>
      <section ref={ref} className="tm-code" aria-label={`${from.place} to ${to.place}`}>
        <div className="tm-code__stage">
          <Media slot="route-opening" className="tm-code__media" />
          <p className="tm-display tm-code__text" aria-hidden>
            <span className="tm-code__from">{code[0]}</span> <span className="tm-code__dash">—</span>{" "}
            <span className="tm-code__to">{code[1]}</span>
          </p>
          <div className="tm-code__fade" aria-hidden />
        </div>
      </section>
      <section className="tm-lines tm-after">
        <div className="tm-after__rule">
          <p>
            {from.coords}
            <span>{from.place}</span>
          </p>
          <p className="text-right">
            {to.coords}
            <span>{to.place}</span>
          </p>
        </div>
        <h2 className="tm-serif-h tm-serif-h--lg text-center" data-reveal="rise">
          <Rise text={heading} />
        </h2>
        <p className="tm-after__text" data-reveal style={{ "--i": 2 } as React.CSSProperties}>
          {text}
        </p>
      </section>
    </>
  );
}

const ROUTE_PATH = "M500 150 C 300 330, 680 600, 500 880";
/** Where each stage sits along the route, 0 to 1. */
const STAGE_AT = [0.08, 0.36, 0.62, 0.92];

/** The dark map: the route draws as you scroll, and the story of one trip plays out along it. */
export function JourneyMap() {
  const { start, end, stats, stages, example } = homeCopy.route;
  const path = useRef<SVGPathElement>(null);
  const plane = useRef<HTMLDivElement>(null);
  const nodes = useRef<Array<HTMLDivElement | null>>([]);

  useEffect(() => {
    const line = path.current;
    if (!line) return;
    const length = line.getTotalLength();
    STAGE_AT.forEach((at, index) => {
      const node = nodes.current[index];
      const point = line.getPointAtLength(length * at);
      if (node) {
        node.style.left = `${point.x / 10}%`;
        node.style.top = `${point.y / 10}%`;
      }
    });
  }, []);

  const ref = useScrollProgress<HTMLElement>("pin", (p, el) => {
    const line = path.current;
    if (!line) return;
    const point = line.getPointAtLength(line.getTotalLength() * p);
    if (plane.current) {
      plane.current.style.left = `${point.x / 10}%`;
      plane.current.style.top = `${point.y / 10}%`;
    }
    const stage = STAGE_AT.reduce((current, at, index) => (p >= at - 0.02 ? index : current), 0);
    el.setAttribute("data-stage", String(stage));
    nodes.current.forEach((node, index) => node?.toggleAttribute("data-on", p >= STAGE_AT[index] - 0.02));
  });

  return (
    <section ref={ref} className="tm-map" data-stage="0" aria-label={example}>
      <div className="tm-map__stage">
        <Media slot="route-origin" sizes="60vw" className="tm-map__land tm-map__land--top" />
        <Media slot="route-destination" sizes="60vw" className="tm-map__land tm-map__land--bottom" />
        <div className="tm-map__route">
          <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" className="tm-map__svg" aria-hidden>
            <path d={ROUTE_PATH} className="tm-map__ghost" vectorEffect="non-scaling-stroke" />
            <path ref={path} d={ROUTE_PATH} pathLength={1} className="tm-map__line" vectorEffect="non-scaling-stroke" />
          </svg>
          {stages.map((stage, index) => (
            <div
              key={stage.name}
              ref={(node) => {
                nodes.current[index] = node;
              }}
              className="tm-map__node"
              data-alert={stage.alert}
              aria-hidden
            />
          ))}
          <div ref={plane} className="tm-map__plane" aria-hidden />

          <p className="tm-map__place tm-map__place--start">
            <em className="tm-italic">{start.label}</em>
            <span>{start.place}</span>
          </p>
          <p className="tm-map__place tm-map__place--end">
            <em className="tm-italic">{end.label}</em>
            <span>{end.place}</span>
          </p>
        </div>

        <div className="tm-map__stats">
          <p className="tm-label">{example}</p>
          {stats.map((stat) => (
            <div key={stat.label}>
              <p className="tm-italic">{stat.label}</p>
              <p>{stat.value}</p>
            </div>
          ))}
        </div>

        <ol className="tm-map__stages">
          {stages.map((stage, index) => (
            <li key={stage.name} data-index={index} data-alert={stage.alert}>
              <p className="tm-italic">{stage.name}</p>
              <p>{stage.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function FinalCall() {
  const { heading, action } = homeCopy.cta;
  // Also lifts the footer's wordmark as this section moves away and uncovers it.
  const ref = useScrollProgress<HTMLElement>("pass", (p, el) => {
    if (p > 0.45) el.closest(".tm-home")?.querySelector<HTMLElement>(".tm-footer__word")?.style.setProperty("--curtain", p.toFixed(3));
  });
  return (
    <section ref={ref} className="tm-cta">
      <Media slot="cta-landscape" className="tm-cta__media" />
      <div className="tm-cta__body">
        <h2 className="tm-serif-h tm-serif-h--lg" data-reveal="rise">
          <Rise text={heading} />
        </h2>
        <Link href="/plan" className="tm-chip tm-chip--wide">
          {action}
        </Link>
      </div>
    </section>
  );
}

export function HomeFooter() {
  const { setFilmOpen, setHowOpen } = useHome();
  return (
    <div className="tm-footer__columns">
      {homeCopy.menu.map((group) => (
        <div key={group.title}>
          <p className="tm-italic">{group.title}</p>
          <ul>
            {group.links.map((link) => (
              <li key={link.href}>
                <Link href={link.href}>{link.label}</Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <div className="tm-footer__tiles">
        <button type="button" className="tm-footer__film" data-cursor="Play" onClick={() => setFilmOpen(true)}>
          <Media slot="cta-landscape" sizes="30vw" />
          <span>{homeCopy.hero.film}</span>
        </button>
        <Link href="/plan">{homeCopy.cta.action}</Link>
        <button type="button" onClick={() => setHowOpen(true)}>
          {homeCopy.how.heading}
        </button>
      </div>
    </div>
  );
}
