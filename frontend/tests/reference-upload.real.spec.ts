import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

/**
 * Real browser reference enrollment.
 * The upload API is not mocked. Cloudinary may be the live storage account
 * when credentials are configured; otherwise the test fails closed.
 */
test.use({
  baseURL: process.env.EG_BASE_URL || "http://localhost:3000",
  channel: "msedge",
  headless: true,
});

function adminToken(): string {
  const backend = path.resolve(__dirname, "../../backend");
  const python = path.join(backend, ".venv", "Scripts", "python.exe");
  const code = [
    "from datetime import timedelta",
    "from app.auth import create_access_token",
    "print(create_access_token({'sub':'1','role':'ADMIN','email':'qa@examguard.local','full_name':'QA'}, expires_delta=timedelta(hours=1)))",
  ].join("; ");
  return execFileSync(python, ["-c", code], { cwd: backend, encoding: "utf8" }).trim();
}

test("enrolls a reference photo per demo candidate and keeps it after reload", async ({ page }) => {
  test.setTimeout(180000);
  const token = adminToken();
  const png = fs.readFileSync(path.resolve(__dirname, "../../test_hall_ticket.png"));
  const replacement = Buffer.from(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c4944415408d763f80f00000101010018dd8db40000000049454e44ae426082",
    "hex"
  );
  const uploads: { attemptId: number; url: string }[] = [];

  page.on("response", async (res) => {
    if (!res.url().includes("/api/v1/demo/upload-reference-face") || res.request().method() !== "POST") return;
    const body = await res.json().catch(() => null);
    let attemptId = 0;
    try {
      attemptId = JSON.parse(res.request().postData() || "{}").attempt_id;
    } catch {
      attemptId = 0;
    }
    uploads.push({
      attemptId,
      url: body?.reference_face_url || "",
    });
    expect(res.status(), JSON.stringify(body)).toBe(200);
    expect(body.reference_face_url).toMatch(/^https:\/\/res\.cloudinary\.com\//);
    expect(body.attempt_id).toBe(attemptId);
  });

  const statusReady = page.waitForResponse((resp) => resp.url().includes("/api/v1/demo/status"), { timeout: 30000 });
  await page.goto(`/dashboard?eg_token=${encodeURIComponent(token)}`);
  await statusReady;
  const load = page.getByRole("button", { name: /^Load Demo Data$/i });
  const demoReady = page.getByText("DEMO001").first();
  if (!(await demoReady.isVisible().catch(() => false))) {
    if (await load.isVisible().catch(() => false)) await load.click();
  }
  await expect(demoReady).toBeVisible({ timeout: 120000 });

  async function card(usn: string) {
    return page.locator(`article[data-usn="${usn}"]`);
  }

  async function chooseAndSave(usn: string, filename: string, bytes: Buffer = png) {
    const panel = await card(usn);
    const enrolledBefore = (await panel.getAttribute("data-enrolled")) === "true";
    const [chooser] = await Promise.all([
      page.waitForEvent("filechooser"),
      panel.locator(".eg-ref-choose").click(),
    ]);
    await chooser.setFiles({ name: filename, mimeType: "image/png", buffer: bytes });
    await expect(panel.locator(".eg-ref-filename")).toHaveAttribute("title", filename);
    await expect(panel.locator(".eg-ref-badge")).toHaveCount(1);
    await expect(panel.locator(".eg-ref-badge")).toHaveText(
      enrolledBefore ? "REFERENCE ENROLLED" : "REFERENCE NOT ENROLLED"
    );
    const save = panel.locator(".eg-ref-save");
    await expect(save).toBeEnabled();
    await save.click();
    await expect(panel.locator(".eg-ref-badge")).toHaveText("REFERENCE ENROLLED", { timeout: 40000 });
    await expect(panel.locator(".eg-ref-badge")).toHaveCount(1);
    await expect(panel.locator(".eg-ref-save")).toHaveCount(0);
  }

  const before = await page.locator("article.eg-ref-card").count();
  expect(before).toBeGreaterThanOrEqual(3);

  async function imageSrc(usn: string) {
    const img = (await card(usn)).locator("img");
    if ((await img.count()) === 0) return null;
    return img.first().getAttribute("src");
  }
  const demo2Before = await imageSrc("DEMO002");
  await chooseAndSave("DEMO001", "WhatsApp Image 2026-09-26 at 10.31.31 PM.png");
  expect(await imageSrc("DEMO002")).toBe(demo2Before);

  await chooseAndSave("DEMO002", "demo-two.png");
  await chooseAndSave("DEMO003", "demo-three.png");

  const firstUrl = uploads[0].url;
  await page.reload();
  await expect(page.getByText("DEMO001").first()).toBeVisible({ timeout: 20000 });
  for (const usn of ["DEMO001", "DEMO002", "DEMO003"]) {
    const panel = await card(usn);
    await expect(panel.locator(".eg-ref-badge")).toHaveCount(1);
    await expect(panel.locator(".eg-ref-badge")).toHaveText("REFERENCE ENROLLED");
    await expect(panel.locator("img")).toHaveAttribute("src", /^https:\/\//);
  }
  expect(await imageSrc("DEMO001")).toBe(firstUrl);

  const demo1Before = await imageSrc("DEMO001");
  const demo3Before = await imageSrc("DEMO003");
  const demo2Url = uploads.find((u) => u.attemptId !== uploads[0].attemptId)?.url;
  await chooseAndSave("DEMO002", "replacement-face.png", replacement);
  expect(uploads[uploads.length - 1].url).not.toBe(demo2Url);
  expect(await imageSrc("DEMO001")).toBe(demo1Before);
  expect(await imageSrc("DEMO003")).toBe(demo3Before);

  async function assertLayout() {
    const layout = await page.evaluate(() => {
      const cards = [...document.querySelectorAll("article.eg-ref-card")].map((card) => {
        const r = card.getBoundingClientRect();
        const file = card.querySelector(".eg-ref-filename")?.getBoundingClientRect();
        const choose = card.querySelector(".eg-ref-choose")?.getBoundingClientRect();
        const save = card.querySelector(".eg-ref-save")?.getBoundingClientRect();
        const inside = (box: DOMRect | undefined) =>
          !box || (box.left >= r.left - 1 && box.right <= r.right + 1 && box.top >= r.top - 1 && box.bottom <= r.bottom + 1);
        const overlaps = (a?: DOMRect, b?: DOMRect) =>
          Boolean(a && b && a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1);
        return {
          usn: card.getAttribute("data-usn"),
          badges: card.querySelectorAll(".eg-ref-badge").length,
          x: r.x,
          y: r.y,
          right: r.right,
          bottom: r.bottom,
          fileInside: inside(file),
          chooseInside: inside(choose),
          saveInside: inside(save),
          fileOverlapsChoose: overlaps(file, choose),
        };
      });
      const overlaps: string[] = [];
      for (let i = 0; i < cards.length; i++) {
        for (let j = i + 1; j < cards.length; j++) {
          const a = cards[i];
          const b = cards[j];
          if (a.x < b.right - 1 && b.x < a.right - 1 && a.y < b.bottom - 1 && b.y < a.bottom - 1) {
            overlaps.push(`${a.usn}+${b.usn}`);
          }
        }
      }
      return {
        cards,
        overlaps,
        scroll: document.documentElement.scrollWidth,
        client: document.documentElement.clientWidth,
      };
    });
    expect(layout.overlaps, JSON.stringify(layout.cards)).toEqual([]);
    expect(layout.scroll).toBeLessThanOrEqual(layout.client + 1);
    for (const card of layout.cards) {
      expect(card.badges).toBe(1);
      expect(card.fileInside).toBe(true);
      expect(card.chooseInside).toBe(true);
      expect(card.saveInside).toBe(true);
      expect(card.fileOverlapsChoose).toBe(false);
    }
    return layout.cards;
  }

  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    const cards = await assertLayout();
    if (viewport.width >= 1440) {
      const demo = cards.filter((c) => ["DEMO001", "DEMO002", "DEMO003"].includes(c.usn || ""));
      expect(new Set(demo.map((c) => Math.round(c.y))).size).toBe(1);
    }
    if (viewport.width <= 390) {
      const demo = cards.filter((c) => ["DEMO001", "DEMO002", "DEMO003"].includes(c.usn || ""));
      expect(new Set(demo.map((c) => Math.round(c.y))).size).toBe(demo.length);
    }
  }
});
