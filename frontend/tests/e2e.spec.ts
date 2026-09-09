import { test, expect } from "@playwright/test";

const ADMIN_TOKEN = process.env.EG_ADMIN_TOKEN || "";

function authUrl(path: string): string {
  return path.includes("?")
    ? `${path}&eg_token=${ADMIN_TOKEN}`
    : `${path}?eg_token=${ADMIN_TOKEN}`;
}

async function waitForAuth(page: import("@playwright/test").Page, timeout = 8000) {
  await page.waitForFunction(() => {
    const body = document.body?.textContent || "";
    return !body.includes("Sign In Required") && !body.includes("Loading");
  }, { timeout });
}

test.describe("Auth Bypass", () => {
  test("Landing page loads without auth", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=ExamGuard").first()).toBeVisible();
  });

  test("Unauthenticated user sees sign-in on protected page", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForTimeout(3000);
    const content = await page.textContent("body");
    expect(content).toContain("Sign In Required");
  });

  test("Admin token bypasses auth on dashboard", async ({ page }) => {
    await page.goto(authUrl("/dashboard"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).not.toContain("Sign In Required");
    expect(content).toContain("Dashboard");
  });

  test("Admin token bypasses auth on students", async ({ page }) => {
    await page.goto(authUrl("/students"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Students");
  });

  test("Admin token bypasses auth on exams", async ({ page }) => {
    await page.goto(authUrl("/exams"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Exam");
  });

  test("Admin token bypasses auth on exam-halls", async ({ page }) => {
    await page.goto(authUrl("/exam-halls"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toMatch(/Hall|Exam Hall/i);
  });

  test("Admin token bypasses auth on subjects", async ({ page }) => {
    await page.goto(authUrl("/subjects"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Subject");
  });

  test("Admin token bypasses auth on entry-verifications", async ({ page }) => {
    await page.goto(authUrl("/entry-verifications"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Verification");
  });

  test("Admin token bypasses auth on audit", async ({ page }) => {
    await page.goto(authUrl("/audit"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Audit");
  });

  test("Admin token bypasses auth on invigilator", async ({ page }) => {
    await page.goto(authUrl("/invigilator"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toMatch(/invigilator|exam|hall|assignment|no.*assigned|profile/i);
  });

  test("Admin token bypasses auth on exam-prep", async ({ page }) => {
    await page.goto(authUrl("/exam-prep"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toMatch(/Prepare|Examination|Preparation/i);
  });

  test("Admin token bypasses auth on documents", async ({ page }) => {
    await page.goto(authUrl("/documents"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Document");
  });

  test("Admin token bypasses auth on hall-tickets", async ({ page }) => {
    await page.goto(authUrl("/hall-tickets"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Hall Ticket");
  });

  test("Admin token bypasses auth on monitoring", async ({ page }) => {
    await page.goto(authUrl("/monitoring"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toMatch(/Monitor|Live/i);
  });

  test("Admin token bypasses auth on cameras", async ({ page }) => {
    await page.goto(authUrl("/cameras"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Camera");
  });

  test("Admin token bypasses auth on entry-points", async ({ page }) => {
    await page.goto(authUrl("/entry-points"));
    await waitForAuth(page);
    const content = await page.textContent("body");
    expect(content).toContain("Entry Point");
  });
});

test.describe("Navigation smoke test", () => {
  test("Navigate through all nav links", async ({ page }) => {
    await page.goto(authUrl("/dashboard"));
    await waitForAuth(page);

    const links = [
      "/students", "/subjects", "/exams", "/exam-halls",
      "/hall-tickets", "/documents", "/entry-verifications",
      "/invigilator", "/audit", "/cameras", "/entry-points",
      "/exam-prep", "/monitoring",
    ];

    for (const link of links) {
      await page.goto(authUrl(link));
      await waitForAuth(page, 5000);
      const content = await page.textContent("body");
      const hasAuth = !content?.includes("Sign In Required");
      console.log(`${link}: auth=${hasAuth}`);
      expect(hasAuth).toBeTruthy();
    }
  });
});
