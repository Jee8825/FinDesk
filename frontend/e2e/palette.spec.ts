// ⌘K Command Palette — opens, navigates, and surfaces transactions.
import { expect, test } from "@playwright/test";

test("palette opens with ctrl+k and navigates to Forecast", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder(/Jump to a page/);
  await expect(input).toBeVisible();

  await input.fill("forecast");
  await page.keyboard.press("Enter");
  // forecast's terrain chunk is code-split — allow the route transition +
  // chunk fetch under full-suite load
  await expect(page.getByRole("heading", { name: "Forecast" })).toBeVisible({
    timeout: 15_000,
  });
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
  // a previous spec's run may still be draining — wait for quiet instead of
  // asserting it (order-dependent flake seen twice in full-suite runs)
  await expect(page.locator("[data-agent-live]")).toHaveCount(0, { timeout: 30_000 });

  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder(/Jump to a page/);
  await input.fill("run scan for anomalies");
  await page.keyboard.press("Enter");

  // queued run flips the shell attribute; beam CSS keys off it
  await expect(page.locator('[data-agent-live="true"]')).toHaveCount(1, { timeout: 10_000 });
});
