"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getEntryVerification,
  beginEntryVerification,
  processHallTicketCheck,
  processSeatCheck,
  processIdentityCheck,
  evaluateEntryVerification,
  escalateEntryVerification,
  resolveEntryVerification,
  type EntryVerification,
  ApiError,
} from "@/lib/entry-verification-api";

const STATUS_CLASSES: Record<string, string> = {
  PENDING: "border-white/20 text-[var(--text-secondary)]",
  IN_PROGRESS: "border-white/30 text-white",
  GRANTED: "border-white/40 text-white",
  DENIED: "border-white/20 text-[var(--text-secondary)]",
  ESCALATED: "border-white/30 text-white",
};

const CHECK_CLASSES: Record<string, string> = {
  PENDING: "border-white/10 text-[var(--text-muted)]",
  PASSED: "border-white/40 text-white",
  FAILED: "border-white/20 text-[var(--text-secondary)]",
  SKIPPED: "border-white/10 text-[var(--text-muted)]",
};

export default function EntryVerificationDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const [ev, setEv] = useState<EntryVerification | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState("");
  const [actionError, setActionError] = useState("");

  const [showEscalate, setShowEscalate] = useState(false);
  const [escalateReason, setEscalateReason] = useState("");
  const [showResolve, setShowResolve] = useState(false);
  const [resolveReason, setResolveReason] = useState("");

  const fetchEntry = useCallback(async () => {
    try {
      const data = await getEntryVerification(id);
      setEv(data);
      setError("");
    } catch {
      setError("Entry verification not found");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchEntry();
  }, [fetchEntry]);

  async function runAction(
    label: string,
    fn: () => Promise<EntryVerification>,
  ) {
    setActionError("");
    setActionLoading(label);
    try {
      const updated = await fn();
      setEv(updated);
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError(err.message);
      } else {
        setActionError(`${label} failed`);
      }
    } finally {
      setActionLoading("");
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
        <div className="max-w-4xl mx-auto">
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">
              Loading entry verification...
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !ev) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
        <div className="max-w-4xl mx-auto">
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <span className="eg-mono text-red-400">
              {error || "Entry verification not found"}
            </span>
          </div>
          <Link
            href="/entry-verifications"
            className="eg-mono-sm text-white hover:text-[var(--text-secondary)] mt-4 inline-block"
          >
            &larr; Back to list
          </Link>
        </div>
      </div>
    );
  }

  function renderActions() {
    const current = ev!;
    const buttons: React.ReactNode[] = [];

    if (current.status === "PENDING") {
      buttons.push(
        <button
          key="begin"
          onClick={() =>
            runAction("Begin processing", () => beginEntryVerification(current.id))
          }
          disabled={actionLoading !== ""}
          className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
        >
          {actionLoading === "Begin processing" ? "Working..." : "Begin Processing"}
        </button>,
      );
    }

    if (current.status === "IN_PROGRESS" || current.status === "PENDING") {
      buttons.push(
        <button
          key="hall"
          onClick={() =>
            runAction("Hall ticket check", () =>
              processHallTicketCheck(current.id),
            )
          }
          disabled={actionLoading !== ""}
          className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
        >
          {actionLoading === "Hall ticket check"
            ? "Working..."
            : "Hall Ticket Check"}
        </button>,
        <button
          key="seat"
          onClick={() =>
            runAction("Seat check", () => processSeatCheck(current.id))
          }
          disabled={actionLoading !== ""}
          className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
        >
          {actionLoading === "Seat check" ? "Working..." : "Seat Check"}
        </button>,
        <button
          key="identity"
          onClick={() =>
            runAction("Identity check", () => processIdentityCheck(current.id))
          }
          disabled={actionLoading !== ""}
          className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
        >
          {actionLoading === "Identity check"
            ? "Working..."
            : "Identity Check"}
        </button>,
        <button
          key="evaluate"
          onClick={() =>
            runAction("Evaluate", () => evaluateEntryVerification(current.id))
          }
          disabled={actionLoading !== ""}
          className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
        >
          {actionLoading === "Evaluate" ? "Working..." : "Evaluate"}
        </button>,
      );
    }

    if (
      current.status !== "ESCALATED" &&
      current.status !== "GRANTED" &&
      current.status !== "DENIED"
    ) {
      buttons.push(
        <button
          key="escalate"
          onClick={() => setShowEscalate(true)}
          disabled={actionLoading !== ""}
          className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
        >
          Escalate
        </button>,
      );
    }

    if (current.status === "ESCALATED") {
      buttons.push(
        <button
          key="resolve-grant"
          onClick={() => setShowResolve(true)}
          disabled={actionLoading !== ""}
          className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
        >
          Resolve
        </button>,
      );
    }

    return buttons;
  }

  if (!ev) return null;

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/entry-verifications"
          className="eg-mono-sm text-[var(--text-secondary)] hover:text-white mb-4 inline-block"
        >
          &larr; Entry Verifications
        </Link>

        <div className="flex items-center gap-4 mb-2">
          <h1 className="eg-display text-3xl">
            Entry Verification #{ev.id}
          </h1>
          <span
            className={`text-[11px] eg-mono border px-3 py-1 ${
              STATUS_CLASSES[ev.status] ||
              "border-white/10 text-[var(--text-muted)]"
            }`}
          >
            {ev.status}
          </span>
        </div>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Created {new Date(ev.created_at).toLocaleString()}
        </p>

        {actionError && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-4 mb-6">
            <span className="eg-mono text-sm text-red-400">{actionError}</span>
          </div>
        )}

        {showEscalate && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              runAction("Escalate", () =>
                escalateEntryVerification(ev.id, escalateReason),
              ).then(() => {
                setShowEscalate(false);
                setEscalateReason("");
              });
            }}
            className="border border-white/10 bg-[var(--bg-raised)] p-6 mb-6"
          >
            <h3 className="eg-mono text-sm text-[var(--text-secondary)] mb-3">
              Escalate for Human Review
            </h3>
            <textarea
              required
              value={escalateReason}
              onChange={(e) => setEscalateReason(e.target.value)}
              placeholder="Reason for escalation..."
              rows={3}
              className="w-full bg-[var(--bg-base)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30 mb-3"
            />
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={actionLoading !== "" || !escalateReason.trim()}
                className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
              >
                {actionLoading === "Escalate" ? "Working..." : "Confirm Escalation"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowEscalate(false);
                  setEscalateReason("");
                }}
                className="eg-btn px-4 py-2 text-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {showResolve && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
            }}
            className="border border-white/10 bg-[var(--bg-raised)] p-6 mb-6"
          >
            <h3 className="eg-mono text-sm text-[var(--text-secondary)] mb-3">
              Resolve Escalation
            </h3>
            {ev.escalation_reason && (
              <div className="border border-white/10 bg-[var(--bg-base)] p-3 mb-3">
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  Reason: {ev.escalation_reason}
                </span>
              </div>
            )}
            <textarea
              value={resolveReason}
              onChange={(e) => setResolveReason(e.target.value)}
              placeholder="Resolution notes (optional)..."
              rows={2}
              className="w-full bg-[var(--bg-base)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30 mb-3"
            />
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() =>
                  runAction("Resolve grant", () =>
                    resolveEntryVerification(ev.id, true, resolveReason),
                  ).then(() => {
                    setShowResolve(false);
                    setResolveReason("");
                  })
                }
                disabled={actionLoading !== ""}
                className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
              >
                {actionLoading === "Resolve grant" ? "Working..." : "Grant Entry"}
              </button>
              <button
                type="button"
                onClick={() =>
                  runAction("Resolve deny", () =>
                    resolveEntryVerification(ev.id, false, resolveReason),
                  ).then(() => {
                    setShowResolve(false);
                    setResolveReason("");
                  })
                }
                disabled={actionLoading !== ""}
                className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
              >
                {actionLoading === "Resolve deny" ? "Working..." : "Deny Entry"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowResolve(false);
                  setResolveReason("");
                }}
                className="eg-btn px-4 py-2 text-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        <div className="flex flex-wrap gap-3 mb-8">{renderActions()}</div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="border border-white/10 bg-[var(--bg-raised)] p-6">
            <h2 className="eg-mono text-sm text-[var(--text-secondary)] mb-4">
              References
            </h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">Student</dt>
                <dd className="font-mono">#{ev.student_id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">Registration</dt>
                <dd className="font-mono">#{ev.exam_registration_id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">Entry Point</dt>
                <dd className="font-mono">#{ev.entry_point_id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">Exam Hall</dt>
                <dd className="font-mono">#{ev.exam_hall_id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">Camera</dt>
                <dd className="font-mono">
                  {ev.camera_id !== null ? `#${ev.camera_id}` : "—"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">Hall Ticket</dt>
                <dd className="font-mono">
                  {ev.hall_ticket_id !== null ? `#${ev.hall_ticket_id}` : "—"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">
                  Identity Attempt
                </dt>
                <dd className="font-mono">
                  {ev.identity_verification_attempt_id !== null
                    ? `#${ev.identity_verification_attempt_id}`
                    : "—"}
                </dd>
              </div>
            </dl>
          </div>

          <div className="border border-white/10 bg-[var(--bg-raised)] p-6">
            <h2 className="eg-mono text-sm text-[var(--text-secondary)] mb-4">
              Checks
            </h2>
            <dl className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">
                  Hall Ticket
                </dt>
                <dd>
                  <span
                    className={`text-[10px] eg-mono border px-2 py-0.5 ${
                      CHECK_CLASSES[ev.hall_ticket_check] ||
                      "border-white/10 text-[var(--text-muted)]"
                    }`}
                  >
                    {ev.hall_ticket_check}
                  </span>
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">Identity</dt>
                <dd>
                  <span
                    className={`text-[10px] eg-mono border px-2 py-0.5 ${
                      CHECK_CLASSES[ev.identity_check] ||
                      "border-white/10 text-[var(--text-muted)]"
                    }`}
                  >
                    {ev.identity_check}
                  </span>
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="eg-mono-sm text-[var(--text-muted)]">Seat</dt>
                <dd>
                  <span
                    className={`text-[10px] eg-mono border px-2 py-0.5 ${
                      CHECK_CLASSES[ev.seat_check] ||
                      "border-white/10 text-[var(--text-muted)]"
                    }`}
                  >
                    {ev.seat_check}
                  </span>
                </dd>
              </div>
            </dl>

            {ev.escalation_reason && (
              <div className="mt-4 pt-4 border-t border-white/10">
                <h3 className="eg-mono-sm text-[var(--text-muted)] mb-1">
                  Escalation Reason
                </h3>
                <p className="text-sm">{ev.escalation_reason}</p>
              </div>
            )}

            {ev.resolved_at && (
              <div className="mt-4 pt-4 border-t border-white/10">
                <h3 className="eg-mono-sm text-[var(--text-muted)] mb-1">
                  Resolved At
                </h3>
                <p className="text-sm font-mono">
                  {new Date(ev.resolved_at).toLocaleString()}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="border border-white/10 bg-[var(--bg-raised)] p-6">
          <h2 className="eg-mono text-sm text-[var(--text-secondary)] mb-4">
            Timestamps
          </h2>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
            <div className="flex justify-between">
              <dt className="eg-mono-sm text-[var(--text-muted)]">Created</dt>
              <dd className="font-mono">
                {new Date(ev.created_at).toLocaleString()}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="eg-mono-sm text-[var(--text-muted)]">Updated</dt>
              <dd className="font-mono">
                {new Date(ev.updated_at).toLocaleString()}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
