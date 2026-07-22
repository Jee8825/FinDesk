// Smoke: every signature surface renders behind auth, the agent-health badge
// reports live, and the sweep's UX additions (recovered strip, inline share
// URL, CA roster) are present. Contract: run against the dev_up.sh stack
// (seeded demo tenant + agents worker + recall memory).
import { expect, test } from "@playwright/test";

const PAGES: Array<{ path: string; heading: string }> = [
  { path: "/", heading: "Dashboard" },
  { path: "/books", heading: "Transactions" },
  { path: "/anomalies", heading: "Anomalies" },
  { path: "/approvals", heading: "Approvals" },
  { path: "/forecast", heading: "Forecast" },
  { path: "/receivables", heading: "45-Day Radar" },
  { path: "/dataroom", heading: "Data Room" },
  { path: "/ca", heading: "Client Roster" },
];

for (const { path, heading } of PAGES) {
  test(`${path} renders "${heading}"`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  });
}

test("agent-health badge reports live worker + memory", async ({ page }) => {
  test.skip(!!process.env.E2E_LITE, "recall memory stack not booted in lite CI");
  await page.goto("/");
  const badge = page.locator('[title="live probe: worker consumer + memory engine"]');
  await expect(badge).toBeVisible();
  // Against a running stack the badge must settle on live, never offline.
  await expect(badge).not.toContainText("offline", { timeout: 15_000 });
});

test("anomalies page shows the recoverable rollup", async ({ page }) => {
  await page.goto("/anomalies");
  // the rollup rail always renders; the recovered-to-date strip only
  // exists once anomalies have been decided (true locally, not on the
  // fresh tenant CI seeds) — assert it only when the data is there
  await expect(page.getByText(/recoverable/i).first()).toBeVisible();
  const strip = page.getByText(/recovered to date/i);
  if ((await strip.count()) > 0) await expect(strip.first()).toBeVisible();
});

test("data room share link renders inline", async ({ page }) => {
  await page.goto("/dataroom");
  await page.getByRole("button", { name: "Generate link" }).click();
  // The URL renders inline in a readonly input (clipboard is best-effort).
  await expect(page.locator('input[value*="/share?token="]')).toBeVisible({ timeout: 10_000 });
});

test("CA roster lists both seeded tenants", async ({ page }) => {
  await page.goto("/ca");
  await expect(page.getByText("Demo Trading Co").first()).toBeVisible();
  await expect(page.getByText("Meridian Textiles Co").first()).toBeVisible();
});

test("/brief composes the daily digest", async ({ page }) => {
  await page.goto("/brief");
  await expect(page.getByRole("heading", { name: "Daily Brief" })).toBeVisible();
  await expect(page.getByText("cash on hand")).toBeVisible();
  await expect(page.getByText(/who owes you/)).toBeVisible();
  await expect(page.getByText("while you were away")).toBeVisible();
});

test("light theme toggles from settings and persists", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByText("appearance")).toBeVisible();

  await page.getByRole("button", { name: "Light", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  // back to the void — and the attribute is gone entirely
  await page.getByRole("button", { name: "Dark", exact: true }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", "light");
});
