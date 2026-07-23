// IMS · ITC Shield: pull the fixture queue, triage renders with deterministic
// recommendations, and an action hands off to the approvals queue (the page
// itself never flips a record — maker-checker is the whole point).
// Data-conditional like payables.spec: sync is idempotent (decided is
// terminal), so accumulated CI state never breaks assertions.
import { expect, test } from "@playwright/test";

test("ims queue pulls fixture records and shows ITC totals", async ({ page }) => {
  await page.goto("/ims");
  await expect(page.getByRole("heading", { name: "IMS · ITC Shield" })).toBeVisible();

  const rows = page.locator("tbody tr");
  if ((await rows.count()) === 0) {
    await page.getByRole("button", { name: /Pull IMS queue/ }).click();
  }
  await expect(rows.first()).toBeVisible();

  // roll-up cards always present once records exist
  await expect(page.getByText("ITC at stake (pending)")).toBeVisible();
  await expect(page.getByText("needs review").first()).toBeVisible();
  // fixture guarantees the exact-match supplier appears
  await expect(page.getByText("Sundaram Packaging").first()).toBeVisible();
  // CA framing ships on every response
  await expect(page.getByText(/maker–checker approval/).first()).toBeVisible();
});

test("accepting a pending record queues an approval, never flips state inline", async ({
  page,
}) => {
  await page.goto("/ims");
  const rows = page.locator("tbody tr");
  if ((await rows.count()) === 0) {
    await page.getByRole("button", { name: /Pull IMS queue/ }).click();
    await expect(rows.first()).toBeVisible();
  }
  const acceptButtons = page.getByRole("button", { name: /accept/ });
  if ((await acceptButtons.count()) === 0) {
    // every record already decided in this environment — nothing to act on
    await expect(page.getByText("decided").first()).toBeVisible();
    return;
  }
  await acceptButtons.first().click();
  // handoff chip appears and links to the approvals control surface
  await expect(page.getByText("queued → approvals").first()).toBeVisible();
});

test("command palette reaches the ims shield", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder(/Jump to a page/);
  await expect(input).toBeVisible();
  await input.fill("ims");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ims/);
  await expect(page.getByRole("heading", { name: "IMS · ITC Shield" })).toBeVisible();
});
