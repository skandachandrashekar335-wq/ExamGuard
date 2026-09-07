"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  getSession,
  startSession,
  endSession,
  cancelSession,
  closeGates,
  openGates,
  listGateEvents,
  type ExaminationSession,
  type GateEvent,
} from "@/lib/session-api";
import AppShell from "@/components/AppShell";

export default function SessionDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const [session, setSession] = useState<ExaminationSession | null>(null);
  const [gateEvents, setGateEvents] = useState<GateEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const [sess, events] = await Promise.all([
        getSession(id),
        listGateEvents(id),
      ]);
      setSession(sess);
      setGateEvents(events.items);
    } catch {
      setError("Failed to load session");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) fetchData();
  }, [id]);

  const handleAction = async (action: () => Promise<unknown>) => {
    setActionLoading(true);
    try {
      await action();
      await fetchData();
    } catch {
      setError("Action failed");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-page-header">
            <span className="eg-mono text-[var(--text-muted)]">Loading...</span>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!session) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-page-header">
            <span className="eg-mono text-[var(--text-muted)]">Session not found</span>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/examination-sessions" className="eg-breadcrumb">
            ← SESSIONS
          </Link>
          <div className="flex items-baseline gap-4">
            <h1 className="eg-page-title">SESSION #{session.id}</h1>
            <span
              className={`eg-badge ${
                session.status === "IN_PROGRESS"
                  ? "eg-badge-success"
                  : session.status === "COMPLETED"
                    ? "eg-badge-neutral"
                    : "eg-badge-info"
              }`}
            >
              {session.status}
            </span>
          </div>
        </div>

        {error && (
          <div className="glass-surface p-4 mb-6">
            <span className="eg-mono text-[var(--text-muted)]">{error}</span>
          </div>
        )}

        {/* Session Info */}
        <div className="glass-surface p-4 mb-6">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="eg-mono-sm text-[var(--text-muted)]">EXAM ID</span>
              <span className="eg-mono-sm ml-2 text-[var(--text-secondary)]">{session.exam_id}</span>
            </div>
            <div>
              <span className="eg-mono-sm text-[var(--text-muted)]">HALL ID</span>
              <span className="eg-mono-sm ml-2 text-[var(--text-secondary)]">{session.exam_hall_id}</span>
            </div>
            <div>
              <span className="eg-mono-sm text-[var(--text-muted)]">GATE STATUS</span>
              <span className="eg-mono-sm ml-2 text-[var(--text-secondary)]">{session.gate_status}</span>
            </div>
            {session.expected_capacity && (
              <div>
                <span className="eg-mono-sm text-[var(--text-muted)]">CAPACITY</span>
                <span className="eg-mono-sm ml-2 text-[var(--text-secondary)]">{session.expected_capacity}</span>
              </div>
            )}
            {session.started_at && (
              <div>
                <span className="eg-mono-sm text-[var(--text-muted)]">STARTED</span>
                <span className="eg-mono-sm ml-2 text-[var(--text-secondary)]">
                  {new Date(session.started_at).toLocaleString()}
                </span>
              </div>
            )}
            {session.ended_at && (
              <div>
                <span className="eg-mono-sm text-[var(--text-muted)]">ENDED</span>
                <span className="eg-mono-sm ml-2 text-[var(--text-secondary)]">
                  {new Date(session.ended_at).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="glass-surface p-4 mb-6">
          <div className="eg-mono-sm text-[var(--text-muted)] mb-3">ACTIONS</div>
          <div className="flex flex-wrap gap-3">
            {session.status === "NOT_STARTED" && (
              <>
                <button
                  onClick={() => handleAction(() => startSession(id))}
                  disabled={actionLoading}
                  className="eg-btn eg-btn-primary"
                >
                  START SESSION
                </button>
                <button
                  onClick={() => handleAction(() => cancelSession(id))}
                  disabled={actionLoading}
                  className="eg-btn eg-btn-danger"
                >
                  CANCEL
                </button>
              </>
            )}
            {session.status === "IN_PROGRESS" && (
              <>
                {session.gate_status === "GATES_OPEN" ? (
                  <button
                    onClick={() => handleAction(() => closeGates(id, "Temporary hold"))}
                    disabled={actionLoading}
                    className="eg-btn"
                  >
                    CLOSE GATES
                  </button>
                ) : (
                  <button
                    onClick={() => handleAction(() => openGates(id, "Resume entry"))}
                    disabled={actionLoading}
                    className="eg-btn eg-btn-primary"
                  >
                    OPEN GATES
                  </button>
                )}
                <button
                  onClick={() => handleAction(() => endSession(id))}
                  disabled={actionLoading}
                  className="eg-btn eg-btn-primary"
                >
                  END SESSION
                </button>
                <button
                  onClick={() => handleAction(() => cancelSession(id))}
                  disabled={actionLoading}
                  className="eg-btn eg-btn-danger"
                >
                  CANCEL
                </button>
              </>
            )}
          </div>
        </div>

        {/* Gate Events */}
        <div className="glass-surface">
          <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
            <span className="eg-mono-sm text-[var(--text-muted)]">
              GATE EVENTS ({gateEvents.length})
            </span>
          </div>
          {gateEvents.length === 0 ? (
            <div className="eg-empty p-4">
              <span className="eg-empty-desc">No gate events recorded</span>
            </div>
          ) : (
            <div>
              {gateEvents.map((evt) => (
                <div
                  key={evt.id}
                  className="px-4 py-3 flex items-start gap-4"
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  <span className="eg-mono-sm shrink-0 text-[var(--text-muted)]">
                    {new Date(evt.created_at).toLocaleString()}
                  </span>
                  <span className="eg-mono-sm shrink-0 text-[var(--text-secondary)]">
                    {evt.previous_status} → {evt.new_status}
                  </span>
                  {evt.reason && (
                    <span className="eg-mono-sm flex-1 text-[var(--text-muted)]">
                      {evt.reason}
                    </span>
                  )}
                  {evt.performed_by && (
                    <span className="eg-mono-sm shrink-0 text-[var(--text-muted)]">
                      BY: {evt.performed_by}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
