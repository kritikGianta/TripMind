import { expect, test, type Page } from "@playwright/test";

import * as about from "../src/content/about";

/** Fail the test on any uncaught browser error, the kind that shows "This page couldn't load". */
function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

async function signIn(page: Page, role: "traveler" | "admin" = "traveler") {
  await page.goto("/sign-in");
  const response = await page.request.post("/api/v1/auth/demo-login", { data: { role } });
  expect(response.ok()).toBeTruthy();
}

test("home, flight search and stay search render without errors", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const day = (await (await page.request.get("/api/v1/datasets/current")).json()).travel_window.first_departure;
  await page.goto(`/flights?from=DEL&fromLabel=Delhi&to=BOM&toLabel=Mumbai&depart=${day}&adults=1&cabin=economy`);
  await expect(page.getByRole("button", { name: /Select|Browse only/ }).first()).toBeVisible();
  await page.goto("/stays");
  await expect(page.getByRole("tab", { name: "Stays" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("home: scroll story, drawers, live prices, and other pages keep their own header", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Where to next?" })).toBeAttached();
  await expect(page.getByRole("link", { name: /Goa.*₹/ })).toBeAttached({ timeout: 30_000 });

  await page.getByRole("button", { name: "Watch the film" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Menu" }).click();
  await expect(page.getByRole("dialog").getByRole("link", { name: "My Trips" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();

  // Real wheel scrolling must move the page, and the drawer tab appears past the hero.
  await page.mouse.move(700, 600);
  await page.mouse.wheel(0, 2600);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(1500);
  await page.getByRole("button", { name: "How it works" }).first().click();
  await expect(page.getByRole("dialog").getByText("3. Hold and pay")).toBeVisible();
  await page.keyboard.press("Escape");

  // Leaving by a link, without a page load, must bring the shared header back.
  await expect(page.getByRole("dialog")).toBeHidden();
  await page.mouse.wheel(0, -400);
  await expect(page.locator(".tm-nav")).not.toHaveAttribute("data-hidden");
  await page.locator(".tm-nav").getByRole("link", { name: "Flights" }).click();
  await expect(page).toHaveURL(/\/flights/);
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "My Trips" })).toBeVisible();
  await expect(page.locator(".tm-home")).toBeHidden();
  expect(errors).toEqual([]);
});

test("home works on a phone with reduced motion, with no sideways scroll", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = watchErrors(page);
  await page.goto(process.env.BASE_URL ?? "http://localhost:3000");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator(".tm-nav").getByRole("link", { name: "Flights" })).toBeHidden();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);

  // The hero film keeps looping even with reduced motion on, and its pause button holds it still.
  const heroVideo = page.locator(".tm-hero video");
  const videoTime = () => heroVideo.evaluate((video: HTMLVideoElement) => video.currentTime);
  const started = await videoTime();
  await expect.poll(videoTime).not.toBe(started);

  // Time passing proves little: a frozen file still reports it. So compare real pixels at points
  // across the loop. Sampling only the first seconds once passed a file that froze after them.
  const slowestChange = await heroVideo.evaluate(async (video: HTMLVideoElement) => {
    const canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 84;
    const context = canvas.getContext("2d", { willReadFrequently: true })!;
    const frameAt = async (fraction: number) => {
      await new Promise((resolve) => {
        video.addEventListener("seeked", resolve, { once: true });
        video.currentTime = video.duration * fraction;
      });
      context.drawImage(video, 0, 0, 160, 84);
      return context.getImageData(0, 0, 160, 84).data;
    };
    const changes: number[] = [];
    let previous = await frameAt(0.3);
    for (const fraction of [0.45, 0.6, 0.75]) {
      const current = await frameAt(fraction);
      changes.push(current.reduce((sum, value, index) => sum + Math.abs(value - previous[index]), 0) / current.length);
      previous = current;
    }
    return Math.min(...changes);
  });
  expect(slowestChange).toBeGreaterThan(1);

  await page.getByRole("button", { name: "Pause background video" }).click();
  await expect.poll(() => heroVideo.evaluate((video: HTMLVideoElement) => video.paused)).toBe(true);
  await page.getByRole("button", { name: "Play background video" }).click();
  await expect.poll(() => heroVideo.evaluate((video: HTMLVideoElement) => video.paused)).toBe(false);

  expect(errors).toEqual([]);
  await context.close();
});

test("home motion: the switch overrides the system, and the scroll effects run", async ({ browser }) => {
  const base = process.env.BASE_URL ?? "http://localhost:3000";
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = watchErrors(page);
  const activeWay = () => page.locator(".tm-way").evaluateAll((ways) => ways.findIndex((way) => way.getAttribute("data-active") === "true"));
  const showWays = () => page.evaluate(() => document.querySelector(".tm-ways")?.scrollIntoView({ behavior: "instant", block: "center" }));

  // With motion off the page is the short, plain layout and nothing plays by itself.
  await page.goto(base);
  const home = page.locator(".tm-home");
  await expect(home).toHaveAttribute("data-motion", "reduced");
  const calmHeight = await page.evaluate(() => document.documentElement.scrollHeight);
  await showWays();
  await page.waitForTimeout(5000);
  expect(await activeWay()).toBe(0);

  // The switch turns everything on, and the choice survives a reload.
  await page.getByRole("button", { name: /Motion off/ }).click();
  await expect(home).toHaveAttribute("data-motion", "full");
  await page.reload();
  await expect(home).toHaveAttribute("data-motion", "full");
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeGreaterThan(calmHeight * 1.4);
  await expect(page.locator("html")).toHaveClass(/lenis/);

  // The accordion now moves on by itself.
  await showWays();
  await expect.poll(activeWay, { timeout: 7000 }).not.toBe(0);

  // Halfway along the destinations, cards sit at different depths and Goa has moved off centre.
  await page.evaluate(() => {
    const section = document.querySelector<HTMLElement>(".tm-dest")!;
    const top = section.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: top + (section.offsetHeight - window.innerHeight) * 0.6, behavior: "instant" });
  });
  const depth = (index: number) => page.locator(".tm-dest__card").nth(index).evaluate((card) => Number((card as HTMLElement).style.getPropertyValue("--d")));
  await expect.poll(() => depth(0)).toBeLessThan(-1);
  await expect.poll(() => depth(4)).toBeGreaterThan(1);

  // Fully through the route code, DEL and GOI have arrived and been drawn together.
  await page.evaluate(() => {
    const section = document.querySelector<HTMLElement>(".tm-code")!;
    window.scrollTo({ top: section.getBoundingClientRect().top + window.scrollY + (section.offsetHeight - window.innerHeight) * 0.5, behavior: "instant" });
  });
  await expect.poll(() => page.locator(".tm-code__from").evaluate((element) => new DOMMatrix(getComputedStyle(element).transform).m41)).toBe(0);

  // Elements that fade in must always end up visible once reached.
  await page.evaluate(() => document.querySelector(".tm-after__text")?.scrollIntoView({ behavior: "instant", block: "center" }));
  await expect(page.locator(".tm-after__text")).toHaveCSS("opacity", "1");
  expect(errors).toEqual([]);
  await context.close();
});

test("about keeps every word of the deck", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/about");
  const shown = ((await page.locator(".ab").textContent()) ?? "").replace(/\s+/g, " ");
  // Paintings are decoration and carry no words; references are checked field by field below.
  const rest: Record<string, unknown> = { ...about };
  delete rest.artwork;
  delete rest.references;
  const { references } = about;
  const strings: string[] = [];
  // Every string in the content file, apart from identifiers and image paths.
  const collect = (value: unknown, key = ""): void => {
    if (typeof value === "string") {
      if (!["id", "referenceId", "status", "src", "page", "attribution"].includes(key)) strings.push(value);
    } else if (Array.isArray(value)) value.forEach((item) => collect(item, key));
    else if (value && typeof value === "object") Object.entries(value).forEach(([name, item]) => collect(item, name));
  };
  collect(rest);
  references.forEach((reference) => strings.push(reference.citation, reference.url, reference.checkedOn));
  strings.push(about.openingQuote.attribution);
  const missing = strings.filter((text) => !shown.includes(text.replace(/\s+/g, " ")));
  expect(missing).toEqual([]);
  expect(strings.length).toBeGreaterThan(200);
  expect(errors).toEqual([]);
});

test("about runs like a presentation: keys, slide list, the how-it-works diagram, build groups, and the shared header returns", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "no-preference" });
  const page = await context.newPage();
  const errors = watchErrors(page);
  await page.goto(`${process.env.BASE_URL ?? "http://localhost:3000"}/about`);
  await expect(page.locator(".ab")).toHaveAttribute("data-ready", "true");
  await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();

  // The first key press lands on the case studies; further presses move them sideways.
  const track = page.locator(".ab-h__track");
  const moved = () => track.evaluate((element) => new DOMMatrix(getComputedStyle(element).transform).m41);
  await page.keyboard.press("ArrowRight");
  await expect(page).toHaveURL(/#case-studies/);
  await expect(page.locator(".ab-dock__count")).toHaveText("02 / 16");
  await page.keyboard.press("ArrowRight");
  await expect.poll(moved).toBeLessThan(-200);

  // Rows fade in only when reached, and must end up visible.
  await page.getByRole("button", { name: "All slides" }).click();
  const slides = page.getByRole("navigation", { name: "Slides" }).getByRole("link");
  await expect(slides).toHaveCount(16);
  await slides.filter({ hasText: "Objectives" }).click();
  await expect(page).toHaveURL(/#objectives/);
  await expect(page.locator("#objectives .ab-row").first()).toHaveCSS("opacity", "1");

  // A pinned scene has to reach its final state from scrolling alone.
  await page.goto(`${process.env.BASE_URL ?? "http://localhost:3000"}/about#closing`);
  await expect(page.locator(".ab-dock__count")).toHaveText("15 / 16");
  await page.mouse.move(700, 500);
  await page.mouse.wheel(0, 1800);
  await expect.poll(() => page.locator(".ab-close__line").evaluate((element) => Number(getComputedStyle(element).opacity))).toBe(1);

  // How it works: one caption at a time, and the keyboard walks it to its last step. A fresh load,
  // because a same-page hash change leaves smooth scrolling where it was.
  await page.goto("about:blank");
  await page.goto(`${process.env.BASE_URL ?? "http://localhost:3000"}/about#workflow`);
  await expect(page.locator(".ab")).toHaveAttribute("data-ready", "true");
  const captions = page.locator(".ab-how__steps > li");
  await expect(captions).toHaveCount(about.workflow.steps.length);
  const opacity = (index: number) => captions.nth(index).evaluate((element) => Number(getComputedStyle(element).opacity));
  await expect.poll(() => opacity(0)).toBe(1);
  expect(await opacity(1)).toBe(0);
  for (let press = 1; press < about.workflow.steps.length; press++) await page.keyboard.press("ArrowRight");
  await expect.poll(() => opacity(about.workflow.steps.length - 1), { timeout: 20_000 }).toBe(1);
  expect(await opacity(0)).toBe(0);

  // Build status comes in groups, each with a summary.
  await page.goto(`${process.env.BASE_URL ?? "http://localhost:3000"}/about#implementation`);
  await expect(page.locator("#implementation .ab-group")).toHaveCount(about.capabilityGroups.length);

  await page.locator(".ab-foot").getByRole("link", { name: "Flights" }).click();
  await expect(page).toHaveURL(/\/flights/);
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  expect(errors).toEqual([]);
  await context.close();
});

test("about is plain with less motion, can be turned on, and has no sideways scroll on a phone", async ({ browser }) => {
  const base = process.env.BASE_URL ?? "http://localhost:3000";
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = watchErrors(page);
  await page.goto(`${base}/about`);
  const root = page.locator(".ab");
  await expect(root).toHaveAttribute("data-motion", "reduced");
  await expect(root).toHaveAttribute("data-layout", "flow");
  await expect(page.locator(".ab-h__track")).toHaveCSS("transform", "none");
  await expect(page.locator(".ab-loader")).toBeHidden();

  // The presenter's choice wins over the system setting, and is remembered.
  await page.getByRole("button", { name: /Motion off/ }).click();
  await expect(root).toHaveAttribute("data-motion", "full");
  await expect(root).toHaveAttribute("data-layout", "stage");
  await page.reload();
  await expect(root).toHaveAttribute("data-motion", "full");
  expect(errors).toEqual([]);
  await context.close();

  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "no-preference", hasTouch: true, isMobile: true });
  const small = await phone.newPage();
  const phoneErrors = watchErrors(small);
  await small.goto(`${base}/about`);
  await expect(small.locator(".ab")).toHaveAttribute("data-layout", "flow");
  const overflow = await small.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  expect(phoneErrors).toEqual([]);
  await phone.close();
});

test("assistant answers and cites its source", async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Ask TripMind" }).click();
  await page.getByRole("button", { name: "Can I cancel my flight for free?" }).click();
  await expect(page.getByText(/AI ·|Help article/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Cancelling a flight").last()).toBeVisible();
  expect(errors).toEqual([]);
});

test("describe your trip fills the planner", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/");
  await page.getByLabel("Describe your trip").fill("2 of us from Delhi to Goa, 3 nights");
  await page.getByRole("button", { name: "Go" }).click();
  await expect(page.getByText(/Delhi → Goa/)).toBeVisible({ timeout: 30_000 });
  expect(errors).toEqual([]);
});

test("signed-in pages render: trips, account, plan, admin consoles", async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page, "admin");
  for (const path of ["/trips", "/account", "/plan", "/admin/imports", "/admin/operations", "/admin/analytics", "/admin/audit"]) {
    await page.goto(path);
    await expect(page.getByRole("heading").first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("group planning: share a plan, vote, see the consensus", async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page);
  const city = await (await page.request.get("/api/v1/locations?q=Mumbai&kind=city")).json();
  const day = (await (await page.request.get("/api/v1/datasets/current")).json()).travel_window.first_departure;
  const back = new Date(Date.parse(`${day}T00:00:00Z`) + 3 * 86_400_000).toISOString().slice(0, 10);
  const plan = await (await page.request.post("/api/v1/plans", {
    data: { origin: "DEL", destination_city_id: city.items[0].value, depart_date: day, return_date: back, adults: 2 },
  })).json();
  await page.goto(`/plans/${plan.id}`);
  await page.getByRole("button", { name: "Plan with friends" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(plan.title);
  await page.getByRole("button", { name: "Love" }).first().click();
  await expect(page.getByText(/1 of 1 voted: 1 love/)).toBeVisible();
  expect(errors).toEqual([]);
});
