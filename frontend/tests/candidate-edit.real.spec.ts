import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

test.use({
  baseURL: process.env.EG_BASE_URL || "http://localhost:3000",
  channel: "msedge",
  headless: true,
  actionTimeout: 15000,
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

function writeShapes(dir: string) {
  const backend = path.resolve(__dirname, "../../backend");
  const python = path.join(backend, ".venv", "Scripts", "python.exe");
  const code = `
import os, struct, zlib, sys
out = sys.argv[1]
def png(w, h, rgb):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\\x00" + bytes(rgb) * w for _ in range(h))
    return b"\\x89PNG\\r\\n\\x1a\\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
open(os.path.join(out, "portrait.png"), "wb").write(png(40, 80, (180, 40, 40)))
open(os.path.join(out, "landscape.png"), "wb").write(png(80, 40, (40, 40, 180)))
open(os.path.join(out, "square.png"), "wb").write(png(48, 48, (40, 140, 60)))
`;
  execFileSync(python, ["-c", code, dir], { cwd: backend });
}

test("edits candidate identity without dropping the reference photo", async ({ page }) => {
  test.setTimeout(240000);
  const token = adminToken();
  const api = process.env.EG_API_URL || "http://127.0.0.1:8000";
  const shapes = fs.mkdtempSync(path.join(os.tmpdir(), "eg-shapes-"));
  writeShapes(shapes);

  const statusReady = page.waitForResponse((resp) => resp.url().includes("/api/v1/demo/status"), { timeout: 30000 });
  await page.goto(`/dashboard?eg_token=${encodeURIComponent(token)}`);
  await statusReady;
  const load = page.getByRole("button", { name: /^Load Demo Data$/i });
  const demoHeading = page.getByText("DEMO001").first();
  if (!(await demoHeading.isVisible().catch(() => false))) {
    if (await load.isVisible().catch(() => false)) await load.click();
  }
  await expect(demoHeading).toBeVisible({ timeout: 120000 });

  const card = (usn: string) => page.locator(`article[data-usn="${usn}"]`);
  const byId = (id: string) => page.locator(`article[data-student-id="${id}"]`);

  const demo1 = await card("DEMO001");
  const studentId = await demo1.getAttribute("data-student-id");
  expect(studentId).toBeTruthy();
  const referenceBefore = (await demo1.locator("img").count())
    ? await demo1.locator("img").first().getAttribute("src")
    : null;
  const demo2Name = ((await card("DEMO002").locator(".eg-ref-card-id span").nth(1).textContent()) || "").trim();
  const demo3Name = ((await card("DEMO003").locator(".eg-ref-card-id span").nth(1).textContent()) || "").trim();

  async function restore() {
    await page.request.patch(`${api}/api/v1/students/${studentId}`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { usn: "DEMO001", name: "Demo Candidate 1" },
    });
  }

  try {
    await demo1.getByRole("button", { name: "Edit" }).click();
    await demo1.getByLabel("Candidate ID / USN").fill("TEST001");
    await demo1.getByLabel("Name").fill("Test Candidate Alpha");
    await demo1.getByRole("button", { name: "Save Changes" }).click();
    await expect(byId(studentId!)).toHaveAttribute("data-usn", "TEST001");
    await expect(byId(studentId!).getByRole("button", { name: "Edit" })).toBeVisible();
    await expect(byId(studentId!).locator(".eg-ref-card-id")).toContainText("Test Candidate Alpha");
    await expect(card("DEMO002").locator(".eg-ref-card-id")).toContainText(demo2Name);
    await expect(card("DEMO003").locator(".eg-ref-card-id")).toContainText(demo3Name);
    if (referenceBefore) {
      await expect(byId(studentId!).locator("img")).toHaveAttribute("src", referenceBefore);
    }

    await page.reload();
    await expect(byId(studentId!)).toHaveAttribute("data-usn", "TEST001", { timeout: 20000 });
    await expect(byId(studentId!).locator(".eg-ref-card-id")).toContainText("Test Candidate Alpha");
    if (referenceBefore) {
      await expect(byId(studentId!).locator("img")).toHaveAttribute("src", referenceBefore);
    }

    const edited = byId(studentId!);
    await edited.getByRole("button", { name: "Edit" }).click();
    await edited.getByLabel("Candidate ID / USN").fill("");
    await edited.getByRole("button", { name: "Save Changes" }).click();
    await expect(edited.getByRole("alert").first()).toBeVisible();
    await edited.getByLabel("Candidate ID / USN").fill("TEST001");
    await edited.getByLabel("Name").fill("   ");
    await edited.getByRole("button", { name: "Save Changes" }).click();
    await expect(edited.locator(`#candidate-name-${studentId}-error`)).toBeVisible();
    await edited.getByLabel("Candidate ID / USN").fill("DEMO002");
    await edited.getByLabel("Name").fill("Test Candidate Alpha");
    await edited.getByRole("button", { name: "Save Changes" }).click();
    await expect(edited.locator(".eg-ref-message")).toContainText(/already exists/i);
    await edited.getByRole("button", { name: "Cancel" }).click();
    await expect(edited).toHaveAttribute("data-usn", "TEST001");

    await edited.getByRole("button", { name: "Edit" }).click();
    await page.route("**/api/v1/students/**", (route) => {
      if (route.request().method() === "PATCH") {
        return route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid or expired token" }),
        });
      }
      return route.continue();
    });
    await edited.getByLabel("Name").fill("Should Not Save");
    await edited.getByRole("button", { name: "Save Changes" }).click();
    await expect(edited.locator(".eg-ref-message")).toContainText(/expired token/i);
    await expect(edited.getByRole("button", { name: "Save Changes" })).toBeEnabled();
    await page.unroute("**/api/v1/students/**");
    await edited.getByRole("button", { name: "Cancel" }).click();

    await edited.getByRole("button", { name: "Edit" }).click();
    await edited.getByLabel("Candidate ID / USN").fill("DEMO001");
    await edited.getByLabel("Name").fill("Demo Candidate 1");
    await edited.getByRole("button", { name: "Save Changes" }).click();
    await expect(byId(studentId!)).toHaveAttribute("data-usn", "DEMO001");
    await expect(byId(studentId!).getByRole("button", { name: "Edit" })).toBeVisible();
    await page.reload();
    await expect(card("DEMO001")).toBeVisible({ timeout: 20000 });
    await expect(card("DEMO001").locator(".eg-ref-card-id")).toContainText("Demo Candidate 1");

    async function replaceReference(usn: string, filePath: string, width: number, height: number) {
      const panel = card(usn);
      const [chooser] = await Promise.all([
        page.waitForEvent("filechooser"),
        panel.locator(".eg-ref-choose").click(),
      ]);
      await chooser.setFiles(filePath);
      const preview = panel.locator(".eg-ref-photo img");
      await expect(preview).toBeVisible();
      const fit = await preview.evaluate((img) => {
        const style = getComputedStyle(img);
        const box = img.getBoundingClientRect();
        const frame = img.parentElement!.getBoundingClientRect();
        return {
          fit: style.objectFit,
          position: style.objectPosition,
          inside: box.left >= frame.left - 1 && box.right <= frame.right + 1 && box.top >= frame.top - 1 && box.bottom <= frame.bottom + 1,
        };
      });
      expect(fit.fit).toBe("contain");
      expect(fit.position === "center" || fit.position === "50% 50%").toBe(true);
      expect(fit.inside).toBe(true);
      const save = panel.locator(".eg-ref-save");
      if (await save.count()) await save.click();
      await expect(panel.locator(".eg-ref-badge")).toHaveText("REFERENCE ENROLLED", { timeout: 40000 });
      await expect(preview).toHaveAttribute("src", /^https:\/\//, { timeout: 40000 });
      await expect.poll(async () => preview.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(width);
      await expect.poll(async () => preview.evaluate((img: HTMLImageElement) => img.naturalHeight)).toBe(height);
    }

    await replaceReference("DEMO001", path.join(shapes, "portrait.png"), 40, 80);
    const portraitUrl = await card("DEMO001").locator("img").getAttribute("src");
    await replaceReference("DEMO001", path.join(shapes, "landscape.png"), 80, 40);
    const landscapeUrl = await card("DEMO001").locator("img").getAttribute("src");
    expect(landscapeUrl).not.toBe(portraitUrl);
    await expect(card("DEMO001").locator(".eg-ref-card-id")).toContainText("DEMO001");
    await expect(card("DEMO001").locator(".eg-ref-card-id")).toContainText("Demo Candidate 1");
    await replaceReference("DEMO002", path.join(shapes, "square.png"), 48, 48);
    await expect(card("DEMO002")).toHaveAttribute("data-usn", "DEMO002");

    await page.reload();
    await expect(card("DEMO001").locator("img")).toHaveAttribute("src", landscapeUrl!);
    await expect(card("DEMO001").locator(".eg-ref-card-id")).toContainText("Demo Candidate 1");

    const [badChooser] = await Promise.all([
      page.waitForEvent("filechooser"),
      card("DEMO003").locator(".eg-ref-choose").click(),
    ]);
    await badChooser.setFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("not an image") });
    await expect(card("DEMO003").locator(".eg-ref-message")).toContainText(/JPG or PNG/i);

    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 1024, height: 768 },
      { width: 768, height: 1024 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      const layout = await page.evaluate(() => {
        const cards = [...document.querySelectorAll("article.eg-ref-card")].map((node) => {
          const rect = node.getBoundingClientRect();
          const img = node.querySelector(".eg-ref-photo img");
          const style = img ? getComputedStyle(img) : null;
          return {
            usn: node.getAttribute("data-usn"),
            x: rect.x,
            y: rect.y,
            right: rect.right,
            bottom: rect.bottom,
            badge: node.querySelectorAll(".eg-ref-badge").length,
            edit: Boolean(node.querySelector(".eg-ref-edit")),
            fit: style?.objectFit || null,
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
      expect(layout.overlaps).toEqual([]);
      expect(layout.scroll).toBeLessThanOrEqual(layout.client + 1);
      for (const item of layout.cards) {
        expect(item.badge).toBe(1);
        expect(item.edit).toBe(true);
        if (item.fit) expect(item.fit).toBe("contain");
      }
      await page.screenshot({
        path: `test-results/cards-${viewport.width}x${viewport.height}.png`,
        fullPage: false,
      });
    }
  } finally {
    await restore();
    fs.rmSync(shapes, { recursive: true, force: true });
  }
});
