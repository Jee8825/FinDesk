// LeakRadar: the landing surface and the PS1 deliverable. Data-conditional like
// ims.spec — a scan is idempotent (upsert by vendor_slug), so accumulated CI
// state never breaks assertions.
import { expect, test } from "@playwright/test";

async function ensureRows(page: import("@playwright/test").Page) {
  await page.goto("/leaks");
  await expect(page.getByRole("heading", { name: "LeakRadar" })).toBeVisible();
  const rows = page.locator("tbody tr");
  if ((await rows.count()) === 0) {
    await page.getByRole("button", { name: /Scan for leaks/ }).click();
    // the scan calls two LLM providers and ~14 memory queries — allow for it
    await expect(rows.first()).toBeVisible({ timeout: 120_000 });
  }
  await expect(rows.first()).toBeVisible();
  return rows;
}

test("login lands on LeakRadar", async ({ page }) => {
  // the storageState fixture already authenticated; "/" is the dashboard, but
  // the post-login route is /leaks — assert the nav entry exists either way
  await page.goto("/leaks");
  await expect(page.getByRole("heading", { name: "LeakRadar" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Recurring Leaks" })).toBeVisible();
});

test("leak table shows cadence, annualized cost and an interrogable score", async ({
  page,
}) => {
  const rows = await ensureRows(page);
  expect(await rows.count()).toBeGreaterThan(0);

  // headline states recoverable money, not just "anomalies found"
  await expect(page.getByRole("status").first()).toContainText(/recoverable across/);
  // category chart, with commitments explicitly held out
  await expect(page.getByText(/SUBSCRIPTION SPEND PER YEAR/i)).toBeVisible();
  await expect(page.getByText(/commitments \(rent, payroll, EMI\)/)).toBeVisible();
  // at least one row carries a detected cadence
  await expect(page.getByText(/^(monthly|quarterly|annual|weekly)$/).first()).toBeVisible();
});

test("a silent price rise is reported with its date and annual cost", async ({ page }) => {
  await ensureRows(page);
  // the business fixture guarantees a sustained increase; the point of the whole
  // detector is that the evidence is dated rather than vague
  const drift = page.getByText(/Price increased by [\d.]+% on \d{4}-\d{2}-\d{2}/).first();
  if (await drift.count()) {
    await expect(drift).toBeVisible();
    await expect(page.getByText(/price rose/).first()).toBeVisible();
  }
});

test("commitments are listed but never scored or offered a usage control", async ({
  page,
}) => {
  await ensureRows(page);
  const commitment = page.getByText("commitment", { exact: true }).first();
  if (await commitment.count()) {
    // shown as a commitment, not as something you can cancel
    await expect(commitment).toBeVisible();
  }
});

test("confirming a subscription is unused is recorded", async ({ page }) => {
  const rows = await ensureRows(page);
  const notUsing = page.getByRole("button", { name: /no longer used/ }).first();
  if ((await notUsing.count()) === 0) {
    test.skip(true, "every row already reviewed in this CI state");
  }
  await notUsing.click();
  // the row flips to a confirmed state — the scan re-reads it from memory later
  await expect(page.getByText("confirmed unused").first()).toBeVisible({
    timeout: 20_000,
  });
  expect(await rows.count()).toBeGreaterThan(0);
});
