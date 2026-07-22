// 3D Cash Terrain — mounts on /forecast when WebGL is available.
import { expect, test } from "@playwright/test";

test("forecast shows the 3D terrain canvas with orbit hint", async ({ page }) => {
  await page.goto("/forecast");
  await expect(page.getByText(/drag to orbit/)).toBeVisible({ timeout: 15_000 });
  const canvas = page.locator("canvas").last();
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box!.height).toBeGreaterThan(250);
  // fallback escape hatch is offered
  await expect(page.getByRole("button", { name: "classic 2D" })).toBeVisible();
});

test("scenario sandbox morphs the forecast server-side", async ({ page }) => {
  await page.goto("/forecast");
  await expect(page.getByText("scenario sandbox")).toBeVisible({ timeout: 15_000 });

  const whatif = page.waitForResponse(
    (r) => r.url().includes("/forecast/whatif") && r.status() === 200,
  );
  await page.getByLabel("collection delay days").fill("28");
  await whatif;

  await expect(page.getByText("Horizon ends")).toBeVisible();
  await expect(page.getByText("Funding gap")).toBeVisible();
  // reset clears the readout
  await page.getByRole("button", { name: "reset" }).click();
  await expect(page.getByText("Horizon ends")).not.toBeVisible();
});
