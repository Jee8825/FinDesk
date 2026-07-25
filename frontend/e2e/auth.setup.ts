// Logs in once through the real UI and saves storageState (tokens live in
// localStorage — see src/lib/api.ts setTokens) for every smoke spec.
import { expect, test as setup } from "@playwright/test";

const AUTH_FILE = "e2e/.auth/founder.json";

setup("authenticate as seeded founder", async ({ page }) => {
  await page.goto("/login");
  await page.locator("#email").fill("founder@demo.findesk.in");
  await page.locator("#password").fill("demo1234");
  await page.getByRole("button", { name: "Sign in" }).click();

  // Successful login routes to LeakRadar (the product surface a first-time
  // visitor should meet). Asserting the app SHELL rather than a page heading
  // keeps this fixture from breaking again the next time the landing page moves
  // — every authenticated page renders the sidebar.
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "LeakRadar" })).toBeVisible({
    timeout: 15_000,
  });
  await page.context().storageState({ path: AUTH_FILE });
});
