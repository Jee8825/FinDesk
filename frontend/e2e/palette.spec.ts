// ⌘K Command Palette — opens, navigates, and surfaces transactions.
import { expect, test } from "@playwright/test";

test("palette opens with ctrl+k and navigates to Forecast", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder(/Jump to a page/);
  await expect(input).toBeVisible();

  await input.fill("forecast");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Forecast" })).toBeVisible();
  await expect(page).toHaveURL(/\/forecast/);
});

test("palette finds a transaction and jumps to its Why? drawer", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder(/Jump to a page/);
  await expect(input).toBeVisible();

  await input.fill("BLUE TOKAI");
  // narration varies by which statements are loaded (AUG locally, INV041
  // in CI's imported fixture) — any Blue Tokai row proves the jump
  const hit = page.getByText(/NEFT-BLUE TOKAI COFFEE/).first();
  await expect(hit).toBeVisible({ timeout: 10_000 });
  await hit.click();

  // lands on /books?why=<id> and the provenance drawer opens
  await expect(page).toHaveURL(/\/books\?why=/);
  await expect(page.getByText("Every figure answers Why?")).toBeVisible({ timeout: 10_000 });
});

test("ledger beam pulses while an agent run is live", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-agent-live]")).toHaveCount(0);

  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder(/Jump to a page/);
  await input.fill("run scan for anomalies");
  await page.keyboard.press("Enter");

  // queued run flips the shell attribute; beam CSS keys off it
  await expect(page.locator('[data-agent-live="true"]')).toHaveCount(1, { timeout: 10_000 });
});
