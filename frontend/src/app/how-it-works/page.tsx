import Link from "next/link";
import AppShell from "@/components/AppShell";

export const metadata = {
  title: "How ExamGuard Works — ExamGuard",
  description:
    "A plain-language walkthrough of how ExamGuard verifies examination entry: reference photos, camera check-in, identity and liveness checks, human review, and the audit trail.",
};

type Step = {
  title: string;
  body: string[];
  cards?: { heading: string; body: string }[];
  list?: string[];
};

const STEPS: Step[] = [
  {
    title: "The examination is created",
    body: [
      "Examination staff create a session with the subject, date, time, semester, department, exam hall, and seats. Students who are registered for that examination appear in the system with their seat allocation.",
      "Nothing about the student is guessed — the record comes from the institution's own registration data.",
    ],
  },
  {
    title: "A reference photo is enrolled for each candidate",
    body: [
      "Before exam day, staff enroll one clear face photo for each candidate from the dashboard. This photo becomes the candidate's reference face.",
      "The reference photo is what the camera will compare against at the hall door. It can be replaced at any time if a better photo is available.",
    ],
  },
  {
    title: "The invigilator is assigned",
    body: [
      "Each examination session is assigned to an invigilator. Only that invigilator (and administrators) can manage the session, run verification, and view its results.",
    ],
  },
  {
    title: "The session is started",
    body: [
      "On exam day, the invigilator starts the session. The session moves from Not Started to In Progress, and it can only be started once — a second attempt is refused instead of creating a duplicate.",
    ],
  },
  {
    title: "The candidate checks in on camera",
    body: [
      "At the hall, the candidate sits in front of the camera and a live image is captured. Two separate checks run on that image:",
    ],
    cards: [
      {
        heading: "Face Similarity (identity check)",
        body: "Compares the live camera image with the enrolled reference photo and produces a similarity score. The score is a comparison of the two faces — it is not a percentage chance of being the right person.",
      },
      {
        heading: "Live-Person Check (liveness check)",
        body: "Checks that a real person is in front of the camera, rather than a printed photo or a video replayed on a screen. This check is independent of the identity check.",
      },
    ],
  },
  {
    title: "Evidence is collected",
    body: [
      "Both results — identity and liveness — are stored together as an evidence package with the images, scores, and timestamps used for that attempt.",
      "The evidence package is what a reviewer (or an auditor later) can look at. Nothing about the attempt is judged without evidence being kept.",
    ],
  },
  {
    title: "A decision is made — or held for a human",
    body: [
      "The decision engine evaluates the evidence against fixed, server-side thresholds:",
    ],
    list: [
      "Clear identity match and passing liveness — entry is granted (MATCH).",
      "Identity clearly does not match — entry is denied (NO_MATCH).",
      "Scores land in an uncertain middle range — the result is INCONCLUSIVE. An uncertain result never silently becomes a pass or a fail.",
    ],
  },
  {
    title: "Uncertain cases go to a person",
    body: [
      "When a check-in comes back INCONCLUSIVE, the invigilator reviews it. The review panel shows the reference photo, the captured image, the identity and liveness results side by side, and why the automatic decision was inconclusive.",
      "The invigilator then records a decision — Check In (the candidate may enter) or Check Out (the candidate may not enter) — and gives a reason. The system records who decided, when, and why.",
      "The AI never makes the final call on an uncertain case. Human review is always available.",
    ],
  },
  {
    title: "Attendance and the audit trail are recorded",
    body: [
      "Every granted entry, denied entry, and manual review decision is written to the attendance record and to an append-only audit trail of events.",
      "Corrections are appended, not overwritten — the original history stays intact, so any decision can be traced back to its evidence.",
    ],
  },
  {
    title: "The exam runs, then the session is ended",
    body: [
      "While the session is in progress, the invigilator can monitor candidates and their verification history. When the examination finishes, the invigilator ends the session.",
      "The session moves to Completed, the end time is recorded, and the record stays available for review and reporting. Ending a session asks for confirmation first, so it cannot happen by accident.",
    ],
  },
];

export default function HowItWorksPage() {
  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/" className="eg-breadcrumb">
            ← BACK TO EXAMGUARD
          </Link>
          <h1 className="eg-page-title">How ExamGuard Works</h1>
          <p className="eg-page-desc">
            EXAMINATION ENTRY, STEP BY STEP — IN PLAIN LANGUAGE
          </p>
        </div>

        <div className="eg-content-sections">
          <section className="eg-content-section">
            <p className="eg-body">
              ExamGuard verifies who enters an examination hall, and keeps a
              record of every decision it helps produce. This page explains the
              whole flow — from setting up the examination to ending the
              session — without technical jargon.
            </p>
            <p className="eg-body">
              The short version: the system compares a live camera image with
              an enrolled reference photo, checks that a real person is present,
              and hands anything it is not sure about to a human. Every step
              leaves a trace.
            </p>
          </section>

          {STEPS.map((step, index) => (
            <section className="eg-content-section" key={step.title}>
              <h2 className="eg-content-heading">
                {index + 1}. {step.title}
              </h2>
              {step.body.map((paragraph) => (
                <p className="eg-body" key={paragraph}>
                  {paragraph}
                </p>
              ))}
              {step.cards && (
                <div className="eg-content-cards">
                  {step.cards.map((card) => (
                    <div className="glass-surface glass p-4" key={card.heading}>
                      <h3 className="eg-content-subheading">{card.heading}</h3>
                      <p className="eg-body">{card.body}</p>
                    </div>
                  ))}
                </div>
              )}
              {step.list && (
                <ul className="eg-body eg-content-list">
                  {step.list.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}

          <section className="eg-content-section">
            <h2 className="eg-content-heading">
              What ExamGuard does not do
            </h2>
            <ul className="eg-body eg-content-list">
              <li>
                It does not decide who enters on its own — uncertain cases are
                always referred to the invigilator.
              </li>
              <li>
                It does not quietly discard results it dislikes — denied and
                inconclusive attempts stay on the record with their evidence.
              </li>
              <li>
                It does not let one person do everything — candidates,
                invigilators, and administrators each have their own role and
                permissions.
              </li>
            </ul>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">Where to go next</h2>
            <p className="eg-body">
              Questions about how your data is handled are covered in the{" "}
              <Link href="/privacy" className="eg-accent">
                Privacy Policy
              </Link>
              . Terms of use are in the{" "}
              <Link href="/terms" className="eg-accent">
                Terms &amp; Conditions
              </Link>
              .
            </p>
          </section>
        </div>

        <div className="mt-16 pt-8" style={{ borderTop: "1px solid var(--border)" }}>
          <Link href="/" className="eg-btn">
            ← Back to ExamGuard
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
