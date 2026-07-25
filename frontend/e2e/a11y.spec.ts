// FE8: the WCAG claim, CI-enforced. frontend/CLAUDE.md rule 5 says signature
// surfaces hold WCAG 2.1 AA — until now nothing checked it. Serious/critical
// axe violations fail the build; moderate/minor are reported in the trace.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SIGNATURE_SURFACES = [
  { path: "/leaks", name: "leakradar" },
  { path: "/payables", name: "payables shield" },
  { path: "/receivables", name: "45-day radar" },
  { path: "/approvals", name: "approvals" },
  { path: "/ims", name: "ims itc shield" },
  { path: "/runs", name: "run viewer" },
  { path: "/reports", name: "reports + close" },
];

for (const surface of SIGNATURE_SURFACES) {
  test(`a11y: ${surface.name} has no serious/critical violations`, async ({ page }) => {
    await page.goto(surface.path);
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const grave = results.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact ?? ""),
    );
    expect(
      grave.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`),
    ).toEqual([]);
  });
}
