// Payables Shield: buyer-side §15/43B(h) view renders with seeded MSE bills.
// Data-conditional where it must be (CI e2e gotcha: never assume accumulated
// data) — but the page shell and roll-up cards are always present.
import { expect, test } from "@playwright/test";

test("payables shield renders shell, cards and CA framing", async ({ page }) => {
  await page.goto("/payables");
  await expect(page.getByRole("heading", { name: "Payables Shield" })).toBeVisible();
  await expect(page.getByText("open to MSE vendors")).toBeVisible();
  await expect(page.getByText("43B(h) at risk").first()).toBeVisible();
  await expect(page.getByText("§16 interest owed").first()).toBeVisible();
  // CA framing ships on every response — review-before-filing is a guardrail
  await expect(page.getByText(/confirm vendor Udyam status/)).toBeVisible();
});

test("seeded MSE bills show banded rows when present", async ({ page }) => {
  await page.goto("/payables");
  await expect(page.getByRole("heading", { name: "Payables Shield" })).toBeVisible();
  const rows = page.locator("tbody tr");
  if ((await rows.count()) === 0) {
    await expect(page.getByText("No open bills to registered MSE vendors.")).toBeVisible();
    return;
  }
  // seed guarantees one breached bill from Sundaram Packaging (micro)
  await expect(page.getByText("Sundaram Packaging").first()).toBeVisible();
  await expect(page.getByText("breached").first()).toBeVisible();
});

test("command palette reaches the payables shield", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder(/Jump to a page/);
  await expect(input).toBeVisible();
  await input.fill("payables");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/payables/);
  await expect(page.getByRole("heading", { name: "Payables Shield" })).toBeVisible();
});
