import { test, expect, Route, Request } from "@playwright/test";

const ADMIN_TOKEN = process.env.EG_ADMIN_TOKEN || "";
const SHOT_DIR = process.env.EG_SHOT_DIR || "test-results";

const PNG_1PX = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

const CORS_HEADERS: Record<string, string> = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS",
  "access-control-allow-headers": "authorization,content-type",
};

type Decision = "NO_MATCH" | "INCONCLUSIVE";

interface MockState {
  attemptId: number;
  finalDecision: Decision;
  contextCalls: Record<number, number>;
  reviewSubmitted: boolean;
  reviewPosts: Array<{ action?: string; reason?: string }>;
  reverifyCalls: number[];
}

function freshState(finalDecision: Decision): MockState {
  return {
    attemptId: 501,
    finalDecision,
    contextCalls: {},
    reviewSubmitted: false,
    reviewPosts: [],
    reverifyCalls: [],
  };
}

const COMPLETED_AT = "2026-09-26T08:05:00Z";

function attemptJson(id: number, status: string, decision: string) {
  return {
    id,
    student_id: 1,
    exam_registration_id: 101,
    hall_ticket_id: null,
    status,
    verification_method: "FACE",
    decision,
    failure_reason:
      decision === "NO_MATCH" ? "Similarity below threshold" : null,
    reference_face_url: "https://example.com/ref.png",
    created_at: "2026-09-26T08:00:00Z",
    started_at: null,
    completed_at: status === "COMPLETED" ? COMPLETED_AT : null,
  };
}

function evidenceJson(state: MockState, attemptId: number) {
  const similarity = state.finalDecision === "NO_MATCH" ? 0.404 : 0.62;
  return [
    {
      id: 11,
      attempt_id: attemptId,
      signal_type: "similarity_score",
      signal_value: String(similarity),
      provider_name: "uniface",
      provider_version: "4.0.0",
      confidence: similarity,
      details: null,
      created_at: COMPLETED_AT,
    },
    {
      id: 12,
      attempt_id: attemptId,
      signal_type: "liveness",
      signal_value: "PASS",
      provider_name: "uniface",
      provider_version: "4.0.0",
      confidence: 0.99,
      details: null,
      created_at: COMPLETED_AT,
    },
  ];
}

function contextJson(state: MockState, id: number, callNo: number) {
  const base = {
    student: { id: 1, usn: "DEMO001", name: "Ada Lovelace" },
    exam: { id: 10, subject_id: 3, exam_name: "Algorithms Final" },
    match_threshold: 0.85,
  };
  if (callNo <= 1) {
    // Before the probe loop: fresh attempt, nothing decided yet.
    return {
      ...base,
      attempt: attemptJson(id, "CREATED", "PENDING"),
      evidence: [],
    };
  }
  return {
    ...base,
    attempt: attemptJson(id, "COMPLETED", state.finalDecision),
    evidence: evidenceJson(state, id),
  };
}

function dashboardJson() {
  return {
    profile: {
      user_id: 1,
      email: "invigilator@example.com",
      full_name: "Ines Invigilator",
      role: "INVIGILATOR",
      assignment_id: 1,
      exam_id: 10,
      exam_name: "Algorithms Final",
      exam_date: "2026-12-02",
      exam_start_time: "09:00:00",
      exam_end_time: "12:00:00",
      subject_code: "CS401",
      subject_name: "Algorithms",
      hall_id: 1,
      hall_name: "Hall A",
      hall_building: "Main",
      hall_room: "101",
      entry_point_id: null,
      entry_point_name: null,
      entry_point_code: null,
      camera_id: null,
      camera_name: null,
      camera_status: null,
      session_id: 5,
      session_status: "IN_PROGRESS",
      gate_status: "GATES_OPEN",
    },
    session_active: true,
    can_start: false,
    can_end: true,
    verification_count: 1,
    granted_count: 0,
    denied_count: 0,
    escalated_count: 0,
    attendance_count: 0,
    security_event_count: 0,
    recent_verifications: [],
  };
}

function studentsJson(state: MockState) {
  return {
    items: [
      {
        registration_id: 101,
        student_id: 1,
        student_usn: "DEMO001",
        student_name: "Ada Lovelace",
        attempt_id: state.attemptId,
        attempt_status: "CREATED",
        attempt_decision: "PENDING",
        reference_face_url: "https://example.com/ref.png",
      },
    ],
    total: 1,
  };
}

function reviewStatusJson(state: MockState) {
  const event = {
    id: 900,
    student_id: 1,
    exam_id: 10,
    exam_registration_id: 101,
    entry_verification_id: null,
    event_type: "MANUAL_CHECK_IN",
    status_snapshot: "PRESENT",
    recorded_by: "invigilator@example.com",
    reason: "Photo and ID card match",
    created_at: COMPLETED_AT,
  };
  return {
    exam_registration_id: 101,
    review_state: state.reviewSubmitted ? "CHECKED_IN" : "NOT_REVIEWED",
    latest_attempt_id: state.attemptId,
    latest_attempt_decision: "INCONCLUSIVE",
    session_status: "IN_PROGRESS",
    seat_number: "A-7",
    events: state.reviewSubmitted ? [event] : [],
  };
}

async function handleApi(route: Route, state: MockState) {
  const req: Request = route.request();
  const path = new URL(req.url()).pathname;

  const json = (status: number, body: unknown) =>
    route.fulfill({
      status,
      headers: { ...CORS_HEADERS, "content-type": "application/json" },
      body: JSON.stringify(body),
    });

  if (req.method() === "OPTIONS") {
    return route.fulfill({ status: 204, headers: CORS_HEADERS });
  }
  if (path === "/api/v1/invigilator/dashboard") {
    return json(200, dashboardJson());
  }
  if (path === "/api/v1/invigilator/registered-students") {
    return json(200, studentsJson(state));
  }

  const parts = path.split("/");
  // /api/v1/identity-verifications/{id}/{action}
  if (parts[3] === "identity-verifications" && parts.length === 6) {
    const id = Number(parts[4]);
    const action = parts[5];
    if (action === "context") {
      state.contextCalls[id] = (state.contextCalls[id] ?? 0) + 1;
      return json(200, contextJson(state, id, state.contextCalls[id]));
    }
    if (action === "verify-face" || action === "evaluate" || action === "start") {
      const status = action === "start" ? "IN_PROGRESS" : "COMPLETED";
      const decision = action === "evaluate" ? state.finalDecision : "PENDING";
      return json(200, {
        ...(action === "verify-face"
          ? { attempt_id: id, evidence: [] }
          : attemptJson(id, status, decision)),
      });
    }
    if (action === "reverify" && req.method() === "POST") {
      state.reverifyCalls.push(id);
      const freshId = id + 1;
      state.attemptId = freshId;
      return json(201, attemptJson(freshId, "CREATED", "PENDING"));
    }
  }

  if (
    path === "/api/v1/attendance/manual-review/101" &&
    req.method() === "GET"
  ) {
    return json(200, reviewStatusJson(state));
  }
  if (path === "/api/v1/attendance/manual-review" && req.method() === "POST") {
    const body = JSON.parse(req.postData() || "{}");
    state.reviewPosts.push(body);
    state.reviewSubmitted = true;
    return json(200, {
      exam_registration_id: 101,
      review_state: "CHECKED_IN",
      event: {
        id: 900,
        student_id: 1,
        exam_id: 10,
        exam_registration_id: 101,
        entry_verification_id: null,
        event_type: "MANUAL_CHECK_IN",
        status_snapshot: "PRESENT",
        recorded_by: "invigilator@example.com",
        reason: body.reason ?? null,
        created_at: COMPLETED_AT,
      },
      attendance_record_id: 77,
    });
  }

  return json(404, { detail: `not mocked: ${req.method()} ${path}` });
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

async function setup(page: import("@playwright/test").Page, state: MockState) {
  await page.route("**/api/v1/**", (route) => handleApi(route, state));
  // Reference image host — never hit the real network in local runs.
  await page.route("**://example.com/**", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "image/png" },
      body: PNG_1PX,
    }),
  );
  await page.goto(`/invigilator?eg_token=${ADMIN_TOKEN}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(
    page.getByRole("heading", { name: "Invigilator Control Center" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("DEMO001").first()).toBeVisible();
}

async function runToResult(
  page: import("@playwright/test").Page,
  opts: { autoVerify?: boolean } = {},
) {
  const modal = page.locator(".eg-modal-backdrop");
  if (!opts.autoVerify) {
    await page
      .getByRole("button", { name: "Verify Face" })
      .first()
      .click();
    await expect(modal).toBeVisible();
    await expect(
      modal.getByRole("button", { name: "Verify Live Face" }),
    ).toBeVisible({ timeout: 30_000 });
    await modal.getByRole("button", { name: "Verify Live Face" }).click();
  }
  // The done-state result card is identified by its meta block.
  await expect(modal.getByText("Verification time")).toBeVisible({
    timeout: 60_000,
  });
  return modal;
}

test.describe("Decision modal — NO_MATCH hard rule, INCONCLUSIVE review, REVERIFY", () => {
  test.skip(!ADMIN_TOKEN, "EG_ADMIN_TOKEN not set — decision spec skipped");

  test("NO_MATCH shows REVERIFY only — no manual allow buttons", async ({
    page,
  }) => {
    test.setTimeout(150_000);
    const state = freshState("NO_MATCH");
    await setup(page, state);
    const modal = await runToResult(page);

    // Server-authoritative messaging for the hard rule.
    await expect(
      modal.locator(".eg-alert-danger").filter({
        hasText: "manual allow is never available",
      }),
    ).toBeVisible();
    // Match threshold surfaced from the attempt context.
    await expect(modal.getByText("Match threshold: 0.850")).toBeVisible();

    // The ONLY escape hatch for NO_MATCH.
    await expect(
      modal.getByRole("button", { name: "REVERIFY" }),
    ).toBeVisible();
    await expect(
      modal.getByRole("button", { name: "ALLOW ENTRY" }),
    ).toHaveCount(0);
    await expect(
      modal.getByRole("button", { name: "DENY ENTRY" }),
    ).toHaveCount(0);

    await page.screenshot({
      path: `${SHOT_DIR}/qa-no-match-result.png`,
      fullPage: false,
      animations: "disabled",
    });
    await modal.locator(".eg-modal-close").click();
    await expect(modal).toHaveCount(0, { timeout: 15_000 });
  });

  test("INCONCLUSIVE review modal: seat, threshold, reason-gated ALLOW", async ({
    page,
  }) => {
    test.setTimeout(150_000);
    const state = freshState("INCONCLUSIVE");
    await setup(page, state);
    const modal = await runToResult(page);

    await expect(
      modal.locator(".eg-alert").filter({
        hasText: "ALLOW ENTRY or DENY ENTRY",
      }),
    ).toBeVisible();
    await expect(
      modal.getByRole("button", { name: "ALLOW ENTRY" }),
    ).toBeVisible();
    await expect(
      modal.getByRole("button", { name: "DENY ENTRY" }),
    ).toBeVisible();
    await expect(
      modal.getByRole("button", { name: "REVERIFY" }),
    ).toBeVisible();

    // Open the review panel.
    await modal.getByRole("button", { name: "ALLOW ENTRY" }).click();
    await expect(
      page.getByRole("button", { name: "Close review" }),
    ).toBeVisible({ timeout: 15_000 });
    const review = page.locator(".eg-modal-backdrop");

    // Enriched evidence: automated decision, seat, threshold, similarity.
    await expect(review.getByText("INCONCLUSIVE").first()).toBeVisible();
    await expect(review.getByText("A-7")).toBeVisible();
    await expect(review.getByText("0.850")).toBeVisible();
    await expect(review.getByText("0.620")).toBeVisible();
    await expect(review.getByText("PASS").first()).toBeVisible();
    await expect(review.getByText("#501")).toBeVisible();

    // Reason is mandatory.
    await review.getByRole("button", { name: "ALLOW ENTRY" }).click();
    await expect(
      review.getByText("Enter a reason for this decision", {
        exact: false,
      }),
    ).toBeVisible();

    await review
      .locator("#manual-review-reason")
      .fill("Photo and ID card match");
    await review.getByRole("button", { name: "ALLOW ENTRY" }).click();

    // Recorded outcome with the immutable automated result attached.
    // (The success alert and the outcome card both say the phrase.)
    await expect(
      review.getByText("Manual review recorded").first(),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      review.getByText("ALLOW ENTRY — candidate admitted (CHECKED_IN)"),
    ).toBeVisible();
    // formatAutomatedResult: "INCONCLUSIVE · similarity 0.620 · threshold …"
    await expect(review.getByText("· similarity 0.620")).toBeVisible();

    // Server received the required payload (reason included).
    expect(state.reviewPosts).toHaveLength(1);
    expect(state.reviewPosts[0].action).toBe("CHECK_IN");
    expect(state.reviewPosts[0].reason).toBe("Photo and ID card match");

    // REVERIFY remains available on the review panel too.
    await expect(
      review.getByRole("button", { name: "REVERIFY" }),
    ).toBeVisible();

    await page.screenshot({
      path: `${SHOT_DIR}/qa-review-allow-outcome.png`,
      fullPage: false,
      animations: "disabled",
    });
  });

  test("REVERIFY starts a fresh attempt and auto-runs the check", async ({
    page,
  }) => {
    test.setTimeout(150_000);
    const state = freshState("NO_MATCH");
    await setup(page, state);
    const modal = await runToResult(page);

    // Reverify from the NO_MATCH result card. The follow-up attempt
    // resolves differently (inconclusive) — flip the mock before clicking.
    state.finalDecision = "INCONCLUSIVE";
    await modal.getByRole("button", { name: "REVERIFY" }).click();

    // Fresh attempt created server-side (mock) and the camera flow re-runs
    // WITHOUT another button press ([REVERIFY] → [VERIFYING...]). The second
    // attempt resolves to INCONCLUSIVE, whose done-state renders the manual
    // review buttons for the FRESH attempt.
    await expect(
      modal.getByRole("button", { name: "ALLOW ENTRY" }),
    ).toBeVisible({ timeout: 60_000 });
    expect(state.reverifyCalls).toEqual([501]);
    expect(state.attemptId).toBe(502);
    expect(state.contextCalls[502]).toBeGreaterThanOrEqual(2);

    await page.screenshot({
      path: `${SHOT_DIR}/qa-reverify-flow.png`,
      fullPage: false,
      animations: "disabled",
    });
  });
});
