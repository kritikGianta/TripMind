import { expect, test, type Page } from "@playwright/test";

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
