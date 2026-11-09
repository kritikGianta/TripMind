import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/** The full self-service journeys: each one goes through the real screens and the real API. */

const HEADERS = { "X-Requested-With": "tripmind" };
const CARD = { number: "4242 4242 4242 4242", month: "12", year: "2031", cvc: "123", name: "Demo Traveller" };

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

/** A day inside the data's travel window, far enough ahead that changes are still allowed. */
async function travelDay(request: APIRequestContext, ahead = 21) {
  const data = await (await request.get("/api/v1/datasets/current")).json();
  const first = Date.parse(`${data.travel_window.first_departure}T00:00:00Z`);
  const start = Math.max(first, Date.now() + ahead * 86_400_000);
  return new Date(start).toISOString().slice(0, 10);
}

const addDays = (day: string, days: number) => new Date(Date.parse(`${day}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);

async function pay(request: APIRequestContext, bookingId: string) {
  const paid = await request.post(`/api/v1/bookings/${bookingId}/payments`, {
    headers: { ...HEADERS, "Idempotency-Key": crypto.randomUUID() },
    data: { card_number: "4242424242424242", expiry_month: 12, expiry_year: 2031, cvc: "123", cardholder_name: "Demo Traveller" },
  });
  expect(paid.ok(), await paid.text()).toBeTruthy();
}

async function bookFlight(request: APIRequestContext) {
  const day = await travelDay(request);
  const search = await (await request.get(`/api/v1/flights/search?origin=DEL&destination=BOM&departure_date=${day}&adults=1&cabin_class=economy`)).json();
  const offer = search.outbound.offers.find((o: { bookable: boolean }) => o.bookable);
  const created = await request.post("/api/v1/bookings", {
    headers: { ...HEADERS, "Idempotency-Key": crypto.randomUUID() },
    data: {
      items: [{ kind: "flight", offer_id: offer.id, adults: 1 }],
      travellers: [{ first_name: "Demo", last_name: "Traveller", date_of_birth: "1990-01-01" }],
      contact: { email: "demo@tripmind.dev", phone: "+919876543210" },
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const booking = await created.json();
  await pay(request, booking.id);
  return booking as { id: string; reference: string; trip_id: string };
}

async function bookStay(request: APIRequestContext) {
  const day = await travelDay(request, 30);
  const city = (await (await request.get("/api/v1/locations?q=Goa&kind=city")).json()).items[0].value;
  const hotels = await (await request.get(`/api/v1/hotels/search?city=${city}&check_in=${day}&check_out=${addDays(day, 2)}&guests=2&rooms=1`)).json();
  // Non-refundable rooms can't change dates, so this journey needs a room that can.
  let room: { room_type_id: string } | undefined;
  let hotel: { id: string } | undefined;
  for (const candidate of hotels.results) {
    const detail = await (await request.get(`/api/v1/hotels/${candidate.id}?check_in=${day}&check_out=${addDays(day, 2)}&guests=2&rooms=1`)).json();
    room = detail.rooms.find((r: { refundable: boolean; fits_party: boolean; price: unknown }) => r.refundable && r.fits_party && r.price);
    if (room) {
      hotel = candidate;
      break;
    }
  }
  expect(room).toBeTruthy();
  const created = await request.post("/api/v1/bookings", {
    headers: { ...HEADERS, "Idempotency-Key": crypto.randomUUID() },
    data: {
      items: [{ kind: "hotel", room_type_id: room!.room_type_id, check_in: day, check_out: addDays(day, 2), rooms: 1, guests: 2 }],
      travellers: [{ first_name: "Demo", last_name: "Traveller" }, { first_name: "Second", last_name: "Guest" }],
      contact: { email: "demo@tripmind.dev", phone: "+919876543210" },
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const booking = await created.json();
  await pay(request, booking.id);
  return { ...booking, hotelId: hotel!.id, day } as { id: string; hotelId: string; day: string };
}

async function fillCard(page: Page, prefix: string) {
  await page.locator(`#${prefix}-number`).fill(CARD.number);
  await page.locator(`#${prefix}-month`).fill(CARD.month);
  await page.locator(`#${prefix}-year`).fill(CARD.year);
  await page.locator(`#${prefix}-cvc`).fill(CARD.cvc);
  await page.locator(`#${prefix}-name`).fill(CARD.name);
}

test("seats, extras and a flight change on a real booking", async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page);
  const booking = await bookFlight(page.request);
  await page.goto(`/bookings/${booking.id}`);

  // Pick a seat from the map and pay for it.
  await page.getByRole("link", { name: "Seats and extras" }).click();
  await expect(page.getByRole("heading", { name: "Seats and extras" })).toBeVisible();
  // Nothing chosen yet is not an error, and each column letter sits over its seats.
  await expect(page.getByText("Nothing chosen yet.")).toBeVisible();
  await expect(page.getByText("Some fields are invalid")).toBeHidden();
  const letter = await page.locator(".tm-seat-letter").first().boundingBox();
  const firstSeat = await page.locator(".tm-seat-map .tm-seat-row").nth(1).locator(".tm-seat").first().boundingBox();
  expect(Math.abs(letter!.x - firstSeat!.x)).toBeLessThan(2);
  const seat = page.locator("button.tm-seat:not([disabled])").first();
  await seat.click();
  await expect(seat).toHaveAttribute("data-state", "picked");
  await expect(page.getByText("To pay")).toBeVisible();
  // The quote arrives, then either a card is asked for or the seat is free.
  const payButton = page.getByRole("button", { name: /^(Pay |Save choices)/ });
  await expect(payButton).toBeEnabled();
  if (await page.locator("#extras-number").isVisible()) await fillCard(page, "extras");
  await payButton.click();
  await expect(page).toHaveURL(new RegExp(`/bookings/${booking.id}$`));
  await expect(page.getByText(/Demo Traveller: /).first()).toBeVisible();

  // Change to another flight: the cost is shown before anything happens.
  await page.getByRole("button", { name: "Change flight" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/You'll see the full cost/)).toBeVisible();
  const options = dialog.locator("ul button");
  await expect(options.first()).toBeVisible();
  await options.nth((await options.count()) > 1 ? 1 : 0).click();
  await dialog.getByRole("button", { name: "See the cost" }).click();
  await expect(dialog.getByText("Change fee")).toBeVisible();
  if (await dialog.locator("#change-number").isVisible()) await fillCard(page, "change");
  await dialog.getByRole("button", { name: /(and change|Confirm change)/ }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(/Your booking has been updated/)).toBeVisible();
  expect(errors).toEqual([]);
});

test("a trip offers what it is missing and exports to a calendar", async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page);
  const booking = await bookFlight(page.request);
  await page.goto(`/trips/${booking.trip_id}`);
  await expect(page.getByRole("link", { name: "Add to calendar" })).toHaveAttribute("href", `/api/v1/trips/${booking.trip_id}/calendar.ics`);
  const calendar = await page.request.get(`/api/v1/trips/${booking.trip_id}/calendar.ics`);
  expect(calendar.ok()).toBeTruthy();
  expect(await calendar.text()).toContain("BEGIN:VCALENDAR");
  await expect(page.getByRole("heading", { name: "What this trip is missing" })).toBeVisible();
  await page.getByRole("link", { name: "Add to this trip" }).first().click();
  // Whatever is booked from here has to join this trip.
  await expect(page).toHaveURL(new RegExp(`trip=${booking.trip_id}`));
  expect(errors).toEqual([]);
});

test("a stay's dates can change, and a review reaches the server's own rules", async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page);
  const booking = await bookStay(page.request);
  await page.goto(`/bookings/${booking.id}`);
  await page.getByRole("button", { name: "Change dates" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Check-out").fill(addDays(booking.day, 3));
  await dialog.getByRole("button", { name: "See the cost" }).click();
  await expect(dialog.getByText("Change fee")).toBeVisible();
  if (await dialog.locator("#change-number").isVisible()) await fillCard(page, "change");
  await dialog.getByRole("button", { name: /(and change|Confirm change)/ }).click();
  await expect(page.getByText(/Your booking has been updated/)).toBeVisible();

  // Move the browser's clock past check-out: the form appears, and the server refuses a stay still ahead.
  await page.clock.setFixedTime(new Date(Date.parse(`${booking.day}T00:00:00Z`) + 30 * 86_400_000));
  await page.reload();
  await page.getByRole("button", { name: "Write a review" }).click();
  const review = page.getByRole("dialog");
  await review.getByLabel("Your review").fill("A lovely quiet place near the beach with very helpful staff.");
  await review.getByRole("button", { name: "Publish review" }).click();
  await expect(review.getByText(/after you check out/)).toBeVisible();
  expect(errors).toEqual([]);
});

test("save a stay, watch its price, read reviews, and find them in the account", async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page);
  const day = await travelDay(page.request, 40);
  const city = (await (await page.request.get("/api/v1/locations?q=Goa&kind=city")).json()).items[0].value;
  const hotels = await (await page.request.get(`/api/v1/hotels/search?city=${city}&check_in=${day}&check_out=${addDays(day, 3)}&guests=2&rooms=1`)).json();
  const hotel = hotels.results[0];

  await page.goto(`/stays/${hotel.id}?checkIn=${day}&checkOut=${addDays(day, 3)}&guests=2&rooms=1`);
  const save = page.getByRole("button", { name: /^(Save|Saved)$/ });
  await expect(save).toBeEnabled();
  if ((await save.getAttribute("aria-pressed")) === "true") {
    await save.click();
    await expect(save).toHaveAttribute("aria-pressed", "false");
  }
  await save.click();
  await expect(save).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Watch price" }).click();
  await expect(page.getByRole("button", { name: "Watching" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Guest reviews" })).toBeVisible();

  await page.goto("/account?tab=saved");
  await expect(page.getByRole("link", { name: hotel.name })).toBeVisible();
  await page.getByRole("tab", { name: "Price alerts" }).click();
  await expect(page).toHaveURL(/tab=alerts/);
  await expect(page.getByText(new RegExp(hotel.name)).first()).toBeVisible();
  await page.getByRole("button", { name: /^Stop watching/ }).first().click();

  // Recent searches were recorded by the API call above and open again in one click.
  await page.getByRole("tab", { name: "Recent searches" }).click();
  await expect(page.getByRole("link", { name: /Stays in Goa/ }).first()).toBeVisible();
  await page.getByRole("link", { name: /Stays in Goa/ }).first().click();
  await expect(page).toHaveURL(/\/stays\?city=/);
  await expect(page.getByRole("heading", { name: /Stays in Goa/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test("explore adds up trips, and the fare calendar moves the search", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/explore");
  await expect(page.getByRole("heading", { name: /places? from Delhi/ })).toBeVisible();
  const plan = page.getByRole("link", { name: "Plan this trip" }).first();
  await expect(plan).toHaveAttribute("href", /\/plan\?.*dest=/);

  const day = await travelDay(page.request);
  await page.goto(`/flights?from=DEL&fromLabel=Delhi&to=BOM&toLabel=Mumbai&depart=${day}&adults=1&cabin=economy`);
  const calendar = page.getByRole("region", { name: "Fare calendar" });
  await expect(calendar).toBeVisible();
  await calendar.locator("button:not([aria-current]):not([disabled])").first().click();
  await expect(page).not.toHaveURL(new RegExp(`depart=${day}`));
  expect(errors).toEqual([]);
});

test("support: a request is filed, answered by an admin, and the reply reaches the traveller", async ({ browser, page }) => {
  const errors = watchErrors(page);
  await signIn(page);
  const subject = `Bag question ${Date.now()}`;
  await page.goto("/support/new?topic=human_agent");
  await expect(page.getByLabel("Subject")).toHaveValue("I would like to talk to a person");
  await page.getByLabel("Subject").fill(subject);
  await page.getByLabel("Your message").fill("How many checked bags can I bring on my flight next week?");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page).toHaveURL(/\/support\/[0-9a-f-]{36}$/);
  await expect(page.getByText(/Filed under/)).toBeVisible();

  const context = await browser.newContext({ baseURL: process.env.BASE_URL ?? "http://localhost:3000" });
  const admin = await context.newPage();
  const adminErrors = watchErrors(admin);
  await signIn(admin, "admin");
  await admin.goto("/admin/support");
  await admin.getByRole("link", { name: new RegExp(subject) }).click();
  await admin.getByLabel("Reply to the traveller").fill("You can bring one checked bag up to 15 kg.");
  await admin.getByRole("button", { name: "Send reply" }).click();
  await expect(admin.getByText("You can bring one checked bag up to 15 kg.")).toBeVisible();
  expect(adminErrors).toEqual([]);
  await context.close();

  await page.reload();
  await expect(page.getByText("You can bring one checked bag up to 15 kg.")).toBeVisible();
  await page.getByRole("button", { name: "Close request" }).click();
  await expect(page.getByText(/This request is closed/)).toBeVisible();
  expect(errors).toEqual([]);
});

test("a new account can change and reset its password, export its data, and be deleted", async ({ page }) => {
  const errors = watchErrors(page);
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto("/sign-up");
  await page.getByLabel("Full name").fill("Test Person");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("first-password-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).not.toHaveURL(/sign-up/);

  await page.goto("/account?tab=security");
  await page.getByLabel("Current password").fill("first-password-1");
  await page.getByLabel("New password").fill("second-password-2");
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByText(/Password changed/)).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download my data" }).click();
  expect((await download).suggestedFilename()).toBe("tripmind-my-data.json");

  await page.getByRole("button", { name: "Sign out everywhere" }).click();
  await expect(page).toHaveURL(/sign-in/);

  // Forgot it: the demo link stands in for the email outside production.
  await page.getByRole("link", { name: "Forgot your password?" }).click();
  await expect(page).toHaveURL(/forgot-password/);
  // Next keeps the page just left in memory, hidden, so its fields also match by name.
  await page.getByLabel("Email").locator("visible=true").fill(email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  const demoLink = page.getByRole("link", { name: "Demo: reset it now" });
  await expect(demoLink).toBeVisible();
  await demoLink.click();
  await expect(page).toHaveURL(/reset-password/);
  await page.getByLabel("New password").fill("third-password-3");
  await page.getByRole("button", { name: "Set new password" }).click();
  await expect(page).toHaveURL(/sign-in/);

  await page.getByLabel("Email").locator("visible=true").fill(email);
  await page.getByLabel("Password").locator("visible=true").fill("third-password-3");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/sign-in/);

  await page.goto("/account?tab=security");
  await page.getByRole("button", { name: "Delete my account" }).click();
  await page.getByRole("dialog").getByLabel("Password").fill("third-password-3");
  await page.getByRole("button", { name: "Delete for good" }).click();
  await expect(page).toHaveURL(/\/$/);
  const me = await page.request.get("/api/v1/auth/me");
  expect(me.status()).toBe(401);
  expect(errors).toEqual([]);
});

test("admin: models show their numbers, and an account can be disabled and enabled", async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page, "admin");
  await page.goto("/admin/models");
  await expect(page.getByText(/of \d+ models are live/)).toBeVisible();
  await expect(page.getByText("Hotel Ranker", { exact: false }).first()).toBeVisible();

  await page.goto("/admin/users");
  await page.getByLabel("Search accounts").fill("demo@tripmind.dev");
  await page.getByRole("button", { name: "Search" }).click();
  const row = page.locator("div", { hasText: "demo@tripmind.dev" }).locator("button").filter({ hasText: /^(Disable|Enable)$/ }).first();
  await expect(row).toHaveText("Disable");
  await row.click();
  await expect(row).toHaveText("Enable");
  await row.click();
  await expect(row).toHaveText("Disable");
  expect(errors).toEqual([]);
});

test("the film fits its window whole, at any screen shape", async ({ browser }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 2560, height: 1080 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport, baseURL: process.env.BASE_URL ?? "http://localhost:3000" });
    const page = await context.newPage();
    await page.goto("/");
    await page.getByRole("button", { name: "Watch the film" }).first().click();
    const video = page.getByRole("dialog").locator("video");
    await expect(video).toHaveCSS("object-fit", "contain");
    const box = await page.getByRole("dialog").boundingBox();
    expect(box).not.toBeNull();
    // Nothing runs off the screen, and the window is the film's own shape.
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width);
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
    expect(Math.abs(box!.width / box!.height - 16 / 9)).toBeLessThan(0.05);
    await context.close();
  }
});
