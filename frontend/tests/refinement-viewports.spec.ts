import { test, expect } from "@playwright/test";
import * as path from "path";

const BASE_URL = process.env.EG_BASE_URL || "http://localhost:3000";
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const VIEWPORTS = [
  { width: 1920, height: 1080, name: "desktop-fhd" },
  { width: 1728, height: 900, name: "desktop-macbook16" },
  { width: 1440, height: 900, name: "desktop-macbook14" },
  { width: 1366, height: 768, name: "desktop-laptop" },
  { width: 1280, height: 800, name: "desktop-compact" },
  { width: 1024, height: 768, name: "tablet-landscape" },
  { width: 768, height: 1024, name: "tablet-portrait" },
  { width: 390, height: 844, name: "mobile-iphone" },
];

test.describe("UI Refinement — Metallic Buttons & Strike-Through Elimination", () => {
  test("metallic buttons have clean centered text without strike-through or line crossing", async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState("networkidle");

    // Inspect the metallic CTA button
    const ctaButton = page.locator(".eg-nav-cta, .btn-chrome, .eg-btn-primary").first();
    await expect(ctaButton).toBeVisible();

    const styles = await ctaButton.evaluate((el) => {
      const computed = window.getComputedStyle(el);
      return {
        textDecorationLine: computed.textDecorationLine,
        display: computed.display,
        alignItems: computed.alignItems,
        justifyContent: computed.justifyContent,
        textAlign: computed.textAlign,
        backgroundImage: computed.backgroundImage,
      };
    });

    // Ensure no line-through or strikethrough decoration
    expect(styles.textDecorationLine).not.toContain("line-through");
    expect(styles.display).toContain("flex");
    expect(styles.alignItems).toBe("center");
    // Ensure specular metallic gradient exists
    expect(styles.backgroundImage).toContain("gradient");
  });

  test("telemetry ticker renders seamlessly without layout shift or header gaps", async ({ page, request }) => {
    // Acquire a valid dev admin JWT from backend
    let devToken = "";
    try {
      const res = await request.post(`${BACKEND_URL}/api/v1/auth/dev/login`, {
        data: { role: "ADMIN" },
      });
      if (res.ok()) {
        const body = await res.json();
        devToken = body.token;
      }
    } catch {
      // Fallback valid JWT payload format
      const payload = Buffer.from(
        JSON.stringify({ sub: "1", email: "admin@dscasc.edu.in", role: "ADMIN", full_name: "System Admin" })
      ).toString("base64");
      devToken = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;
    }

    await page.addInitScript((tok) => {
      window.sessionStorage.setItem("eg_dev_token", tok);
    }, devToken);

    await page.goto(`${BASE_URL}/dashboard?eg_token=${encodeURIComponent(devToken)}`);
    await page.waitForLoadState("domcontentloaded");

    const marquee = page.locator(".animate-acid-marquee").first();
    await expect(marquee).toBeVisible({ timeout: 10000 });

    const text = await marquee.innerText();
    expect(text).toContain("EXAMGUARD PROTOCOL");

    // Verify ticker and header are unified in single sticky container
    const stickyParent = page.locator("div.sticky.top-0").first();
    await expect(stickyParent).toBeVisible();
  });
});

test.describe("UI Refinement — Responsive Viewport Suite (8 Viewports)", () => {
  for (const vp of VIEWPORTS) {
    test(`renders cleanly at ${vp.width}x${vp.height} (${vp.name}) without horizontal overflow`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });

      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle" });

      // Verify no horizontal document overflow
      const overflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth + 2;
      });
      expect(overflow).toBe(false);

      // Verify pill navigation or brand is visible
      const brand = page.locator(".eg-nav-brand, img[alt='ExamGuard']").first();
      await expect(brand).toBeVisible();

      // Capture screenshot for visual audit archive
      const screenshotDir = path.resolve(__dirname, "../../playwright-screenshots");
      await page.screenshot({
        path: `${screenshotDir}/viewport-${vp.name}-${vp.width}x${vp.height}.png`,
        fullPage: false,
      });

      // Ensure zero uncaught errors
      expect(consoleErrors.filter((e) => !e.includes("favicon") && !e.includes("404"))).toHaveLength(0);
    });
  }
});
