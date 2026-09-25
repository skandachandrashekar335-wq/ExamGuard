import { test, expect, Route, Request } from "@playwright/test";

const INVIGILATOR_TOKEN = process.env.EG_INVIGILATOR_TOKEN || "";
const API_BASE = (
  process.env.EG_API_BASE ||
  "https://examguard-production-ef78.up.railway.app"
).replace(/\/$/, "");
const SHOT_DIR = process.env.EG_SHOT_DIR || "test-results";

type ApiEntry = { method: string; path: string; status: number };

async function passThrough(route: Route, token: string, log: ApiEntry[]) {
  const req: Request = route.request();
  const url = new URL(req.url());
  if (req.method() === "OPTIONS") {
    return route.fulfill({
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS",
        "access-control-allow-headers": "authorization,content-type",
      },
    });
  }
  try {
    const resp = await route.fetch({
      headers: { ...req.headers(), authorization: `Bearer ${token}` },
    });
    log.push({ method: req.method(), path: url.pathname, status: resp.status() });
    return route.fulfill({
      response: resp,
      headers: { ...resp.headers(), "access-control-allow-origin": "*" },
    });
  } catch {
    log.push({ method: req.method(), path: url.pathname, status: 0 });
    return route.abort();
  }
}

test.use({
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
    ],
  },
  permissions: ["camera"],
});

test.describe("Acceptance E — invigilator live verification in a real browser", () => {
  test.skip(
    !INVIGILATOR_TOKEN,
    "EG_INVIGILATOR_TOKEN not set — browser acceptance E not run",
  );

  test("camera modal, recoverable probe error, cleanup after close", async ({
    page,
    request,
  },
  ) => {
    test.setTimeout(240_000);

    const apiLog: ApiEntry[] = [];
    const pageErrors: string[] = [];
    page.on("pageerror", (e) => pageErrors.push(String(e)));
    page.on("console", (m) => {
      if (m.type() === "error") pageErrors.push(`console: ${m.text()}`);
    });

    await page.route("**/api/v1/**", (route) =>
      passThrough(route, INVIGILATOR_TOKEN, apiLog),
    );

    const authHeaders = { authorization: `Bearer ${INVIGILATOR_TOKEN}` };

    const dash = await request.get(
      `${API_BASE}/api/v1/invigilator/registered-students`,
      { headers: authHeaders },
    );
    expect(dash.status(), "invigilator registered-students API").toBe(200);
    const items = (await dash.json()).items as Array<{
      student_usn: string;
      attempt_id: number | null;
      reference_face_url: string | null;
    }>;
    expect(items.length, "registered candidates for assigned exam").toBeGreaterThanOrEqual(3);
    const target = items.find((i) => i.student_usn === "DEMO001");
    expect(target, "DEMO001 present in production data").toBeTruthy();
    expect(target!.attempt_id, "DEMO001 has a verification attempt").toBeTruthy();
    expect(
      target!.reference_face_url,
      "reference face enrolled on DEMO001 attempt (demo prep)",
    ).toMatch(/^https:\/\//);
    const attemptId = target!.attempt_id!;

    const ctxBefore = await request.get(
      `${API_BASE}/api/v1/identity-verifications/${attemptId}/context`,
      { headers: authHeaders },
    );
    expect(ctxBefore.status(), "attempt context before").toBe(200);
    const beforeBody = await ctxBefore.json();
    expect(beforeBody.attempt.status).toBe("CREATED");
    expect(beforeBody.attempt.decision).toBe("PENDING");

    await page.goto(`/invigilator?eg_token=${INVIGILATOR_TOKEN}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByRole("heading", { name: "Invigilator Control Center" }),
    ).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("ExamGuard Demo Examination").first()).toBeVisible();
    await expect(page.getByText("Demo Hall A").first()).toBeVisible();
    await expect(page.getByText("DEMO001").first()).toBeVisible();
    await expect(page.getByText("DEMO002").first()).toBeVisible();
    await expect(page.getByText("DEMO003").first()).toBeVisible();
    await page.screenshot({ path: `${SHOT_DIR}/e1-dashboard.png`, fullPage: true, animations: "disabled" });

    const row = page
      .locator(".space-y-2 > div")
      .filter({ hasText: "DEMO001" })
      .first();
    await row.getByRole("button", { name: "Verify Face" }).click();

    const modal = page.locator(".eg-modal-backdrop");
    await expect(modal).toBeVisible();
    await expect(modal.getByText("Face Verification")).toBeVisible();
    await expect(modal.getByText(/DEMO001/).first()).toBeVisible();
    await expect(modal.locator('img[alt="Reference face"]')).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      modal.getByRole("button", { name: "Verify Live Face" }),
    ).toBeVisible({ timeout: 60_000 });
    await expect(modal.getByText("Camera ready").first()).toBeVisible();
    await page.screenshot({ path: `${SHOT_DIR}/e2-modal-camera-ready.png`, animations: "disabled" });

    const verifyCallsBefore = apiLog.filter(
      (e) => e.path.endsWith("/verify-face") && e.method === "POST",
    ).length;

    await modal.getByRole("button", { name: "Verify Live Face" }).click();

    await expect
      .poll(
        async () =>
          apiLog.filter(
            (e) => e.path.endsWith("/verify-face") && e.method === "POST",
          ).length - verifyCallsBefore,
        { timeout: 90_000, message: "at least two probe cycles against production" },
      )
      .toBeGreaterThanOrEqual(2);

    const probeStatuses = apiLog
      .filter((e) => e.path.endsWith("/verify-face") && e.method === "POST")
      .map((e) => e.status);
    expect(
      probeStatuses.every((s) => s === 422 || s === 400),
      `probe statuses are recoverable client errors: ${JSON.stringify(probeStatuses)}`,
    ).toBe(true);

    await expect(modal.getByText(/no usable face|no face detected/i).first()).toBeVisible({
      timeout: 60_000,
    });
    await expect(
      modal.locator(".eg-alert-danger"),
      "recoverable probe error must not render a terminal error card",
    ).toHaveCount(0);
    await expect(modal.getByText("Verification in progress").first()).toBeVisible();
    await page.screenshot({ path: `${SHOT_DIR}/e3-recoverable-loop.png`, animations: "disabled" });

    const ctxDuring = await request.get(
      `${API_BASE}/api/v1/identity-verifications/${attemptId}/context`,
      { headers: authHeaders },
    );
    const duringBody = await ctxDuring.json();
    expect(
      duringBody.attempt.status,
      "recoverable probe errors must not fail the attempt",
    ).toBe("CREATED");
    expect(duringBody.attempt.decision).toBe("PENDING");

    await modal.locator(".eg-modal-close").click();
    await expect(modal).toHaveCount(0, { timeout: 15_000 });

    const videoState = await page.evaluate(() =>
      Array.from(document.querySelectorAll("video")).map((v) => {
        const stream = v.srcObject as MediaStream | null;
        return {
          hasSrc: Boolean(stream),
          liveTracks: stream
            ? stream.getTracks().filter((t) => t.readyState === "live").length
            : 0,
        };
      }),
    );
    expect(
      videoState.filter((v) => v.liveTracks > 0),
      `camera tracks must be stopped after close: ${JSON.stringify(videoState)}`,
    ).toHaveLength(0);

    const probesAtClose = apiLog.filter(
      (e) => e.path.endsWith("/verify-face") && e.method === "POST",
    ).length;
    await page.waitForTimeout(5_000);
    const probesAfterWait = apiLog.filter(
      (e) => e.path.endsWith("/verify-face") && e.method === "POST",
    ).length;
    expect(
      probesAfterWait,
      "capture loop must stop after closing the modal",
    ).toBe(probesAtClose);

    await row.getByRole("button", { name: "Verify Face" }).click();
    await expect(modal).toBeVisible();
    await expect(
      modal.getByRole("button", { name: "Verify Live Face" }),
    ).toBeVisible({ timeout: 60_000 });
    await modal.locator(".eg-modal-close").click();
    await expect(modal).toHaveCount(0, { timeout: 15_000 });
    const videoState2 = await page.evaluate(() =>
      Array.from(document.querySelectorAll("video")).map((v) => {
        const stream = v.srcObject as MediaStream | null;
        return stream
          ? stream.getTracks().filter((t) => t.readyState === "live").length
          : 0;
      }),
    );
    expect(videoState2.filter((n) => n > 0)).toHaveLength(0);

    const ctxAfter = await request.get(
      `${API_BASE}/api/v1/identity-verifications/${attemptId}/context`,
      { headers: authHeaders },
    );
    const afterBody = await ctxAfter.json();
    expect(afterBody.attempt.status, "attempt untouched by the browser run").toBe("CREATED");
    expect(afterBody.attempt.decision).toBe("PENDING");

    const uncaught = pageErrors.filter((e) => !e.startsWith("console:"));
    const hydrationDevTokenArtifacts = uncaught.filter((e) =>
      e.includes("Hydration failed"),
    );
    const unexpected = uncaught.filter((e) => !e.includes("Hydration failed"));
    expect(
      unexpected,
      `uncaught page errors: ${unexpected.join(" | ")}`,
    ).toHaveLength(0);
    expect(
      hydrationDevTokenArtifacts.length,
      "hydration mismatch is only tolerated because the dev-only eg_token " +
        "bypass resolves auth during SSR hydration; production resolves auth after",
    ).toBeLessThanOrEqual(1);

    console.log(
      `ACCEPTANCE_E probes=${probeStatuses.length} statuses=${JSON.stringify(probeStatuses)} attempt=${attemptId} console_errors=${pageErrors.length} hydration_devtoken=${hydrationDevTokenArtifacts.length}`,
    );
  });
});
