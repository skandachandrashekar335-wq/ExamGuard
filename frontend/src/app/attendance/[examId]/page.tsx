"use client";

import { useEffect, useState, useCallback, Fragment } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  listExamAttendance,
  getAttendanceSummary,
  correctAttendance,
  listEntryEvents,
  type AttendanceRecord,
  type AttendanceSummaryResponse,
  type AttendanceEvent,
  ApiError,
} from "@/lib/attendance-api";
import AppShell from "@/components/AppShell";

const STATUS_BADGE: Record<string, string> = {
  PRESENT: "eg-badge-success",
  ABSENT: "eg-badge-danger",
  EXCUSED: "eg-badge-warning",
  NOT_RECORDED: "eg-badge-neutral",
};

export default function ExamAttendancePage() {
  const params = useParams();
  const examId = Number(params.examId);

  const [summary, setSummary] = useState<AttendanceSummaryResponse | null>(
    null,
  );
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState("");
  const [hallFilter, setHallFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showCorrect, setShowCorrect] = useState<number | null>(null);
  const [correctStatus, setCorrectStatus] = useState("EXCUSED");
  const [correctReason, setCorrectReason] = useState("");
  const [correctBy, setCorrectBy] = useState("");
  const [correctError, setCorrectError] = useState("");
  const [correctLoading, setCorrectLoading] = useState(false);

  const [showEvents, setShowEvents] = useState<number | null>(null);
  const [events, setEvents] = useState<AttendanceEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  const fetchSummary = useCallback(async () => {
    try {
      const s = await getAttendanceSummary(examId);
      setSummary(s);
    } catch {
      // summary unavailable
    }
  }, [examId]);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listExamAttendance(examId, {
        hall_id: hallFilter ? Number(hallFilter) : undefined,
        status: statusFilter || undefined,
        page,
        page_size: pageSize,
      });
      setRecords(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load attendance records");
    } finally {
      setLoading(false);
    }
  }, [examId, hallFilter, statusFilter, page, pageSize]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  const totalPages = Math.ceil(total / pageSize);

  async function handleCorrect(regId: number) {
    setCorrectError("");
    setCorrectLoading(true);
    try {
      await correctAttendance(regId, {
        status: correctStatus,
        reason: correctReason,
        recorded_by: correctBy,
      });
      setShowCorrect(null);
      setCorrectReason("");
      setCorrectBy("");
      fetchRecords();
      fetchSummary();
    } catch (err) {
      if (err instanceof ApiError) {
        setCorrectError(err.message);
      } else {
        setCorrectError("Failed to correct attendance");
      }
    } finally {
      setCorrectLoading(false);
    }
  }

  async function loadEvents(evId: number) {
    if (showEvents === evId) {
      setShowEvents(null);
      return;
    }
    setEventsLoading(true);
    setShowEvents(evId);
    try {
      const data = await listEntryEvents(evId, { page_size: 50 });
      setEvents(data.items);
    } catch {
      setEvents([]);
    } finally {
      setEventsLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/attendance" className="eg-breadcrumb">
            ← Attendance
          </Link>
          <h1 className="eg-page-title">Exam Attendance</h1>
          <p className="eg-page-desc">Exam #{examId}</p>
        </div>

        {summary && (
          <div className="glass-surface p-6 mb-8">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-6">
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Registered
                </div>
                <div className="eg-metric-value">
                  {summary.total_registered}
                </div>
              </div>
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Present
                </div>
                <div className="eg-metric-value">
                  {summary.total_present}
                </div>
              </div>
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Absent
                </div>
                <div className="eg-metric-value">
                  {summary.total_absent}
                </div>
              </div>
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Excused
                </div>
                <div className="eg-metric-value">
                  {summary.total_excused}
                </div>
              </div>
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Rate
                </div>
                <div className="eg-metric-value">
                  {Math.round(summary.attendance_rate)}%
                </div>
              </div>
            </div>

            {summary.by_hall.length > 0 && (
              <div className="mt-6 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-3">
                  By Hall
                </div>
                <div className="flex flex-wrap gap-4">
                  {summary.by_hall.map((h) => (
                    <div
                      key={h.hall_id}
                      className="glass px-4 py-2 text-sm"
                    >
                      <span className="text-[var(--text-primary)]">{h.hall_name}</span>
                      <span className="text-[var(--text-muted)] ml-2">
                        {h.present}/{h.total}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="eg-filter-bar mb-6">
          <input
            type="text"
            placeholder="Hall ID..."
            value={hallFilter}
            onChange={(e) => {
              setHallFilter(e.target.value);
              setPage(1);
            }}
            className="eg-input w-32"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="eg-select"
          >
            <option value="">All statuses</option>
            <option value="PRESENT">Present</option>
            <option value="ABSENT">Absent</option>
            <option value="EXCUSED">Excused</option>
            <option value="NOT_RECORDED">Not Recorded</option>
          </select>
        </div>

        {error && (
          <div className="glass-surface p-4 mb-6">
            <span className="eg-mono text-sm" style={{ color: "var(--danger)" }}>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="glass-surface p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">
              Loading attendance records...
            </span>
          </div>
        ) : records.length === 0 ? (
          <div className="eg-empty">
            <div className="eg-empty-title">No records</div>
            <div className="eg-empty-desc">
              No attendance records found for this exam.
            </div>
          </div>
        ) : (
          <div className="eg-table-wrap">
            <table className="eg-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Student</th>
                  <th>Hall</th>
                  <th>Seat</th>
                  <th>Status</th>
                  <th>Method</th>
                  <th>Entry Time</th>
                  <th>EV</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <Fragment key={r.id}>
                    <tr>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>{r.id}</td>
                      <td>#{r.student_id}</td>
                      <td style={{ color: "var(--text-secondary)" }}>#{r.hall_id}</td>
                      <td style={{ color: "var(--text-secondary)" }}>
                        {r.seat_number ?? "—"}
                      </td>
                      <td>
                        <span className={`eg-badge ${STATUS_BADGE[r.status] || "eg-badge-neutral"}`}>
                          {r.status}
                        </span>
                      </td>
                      <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                        {r.entry_method}
                      </td>
                      <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                        {new Date(r.entry_time).toLocaleString()}
                      </td>
                      <td>
                        <button
                          onClick={() => loadEvents(r.entry_verification_id)}
                          className="eg-mono-sm text-[var(--text-primary)] hover:text-[var(--text-secondary)] transition-colors"
                        >
                          #{r.entry_verification_id}
                        </button>
                      </td>
                      <td className="text-right">
                        <button
                          onClick={() =>
                            setShowCorrect(showCorrect === r.id ? null : r.id)
                          }
                          className="eg-mono-sm text-[var(--text-primary)] hover:text-[var(--text-secondary)] transition-colors"
                        >
                          Correct
                        </button>
                      </td>
                    </tr>
                    {showCorrect === r.id && (
                      <tr key={`${r.id}-correct`}>
                        <td colSpan={9} className="p-4">
                          <div className="glass-surface p-4">
                            <h4 className="eg-mono text-sm text-[var(--text-secondary)] mb-3">
                              Manual Correction — Student #{r.student_id}
                            </h4>
                            {correctError && (
                              <div className="glass-surface p-3 mb-3" style={{ borderColor: "rgba(220,38,38,0.3)" }}>
                                <span className="eg-mono text-sm" style={{ color: "var(--danger)" }}>
                                  {correctError}
                                </span>
                              </div>
                            )}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                              <div>
                                <label className="eg-label">
                                  Status
                                </label>
                                <select
                                  value={correctStatus}
                                  onChange={(e) =>
                                    setCorrectStatus(e.target.value)
                                  }
                                  className="eg-select w-full"
                                >
                                  <option value="EXCUSED">EXCUSED</option>
                                  <option value="PRESENT">PRESENT</option>
                                </select>
                              </div>
                              <div>
                                <label className="eg-label">
                                  Reason *
                                </label>
                                <input
                                  type="text"
                                  required
                                  value={correctReason}
                                  onChange={(e) =>
                                    setCorrectReason(e.target.value)
                                  }
                                  placeholder="Reason for correction"
                                  className="eg-input w-full"
                                />
                              </div>
                              <div>
                                <label className="eg-label">
                                  Corrected By *
                                </label>
                                <input
                                  type="text"
                                  required
                                  value={correctBy}
                                  onChange={(e) => setCorrectBy(e.target.value)}
                                  placeholder="Admin ID"
                                  className="eg-input w-full"
                                />
                              </div>
                            </div>
                            <div className="flex gap-3">
                              <button
                                onClick={() => handleCorrect(r.exam_registration_id)}
                                disabled={
                                  correctLoading ||
                                  !correctReason.trim() ||
                                  !correctBy.trim()
                                }
                                className="eg-btn eg-btn-primary px-4 py-2 text-sm disabled:opacity-30"
                              >
                                {correctLoading ? "Saving..." : "Save Correction"}
                              </button>
                              <button
                                onClick={() => setShowCorrect(null)}
                                className="eg-btn px-4 py-2 text-sm"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                    {showEvents === r.entry_verification_id && (
                      <tr
                        key={`${r.id}-events`}
                      >
                        <td colSpan={9} className="p-4">
                          <div className="glass-surface p-4">
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="eg-mono text-sm text-[var(--text-secondary)]">
                                Events for EV #{r.entry_verification_id}
                              </h4>
                              <Link
                                href={`/attendance/events/${r.entry_verification_id}`}
                                className="eg-mono-sm text-[var(--text-primary)] hover:text-[var(--text-secondary)] transition-colors"
                              >
                                Full History →
                              </Link>
                            </div>
                            {eventsLoading ? (
                              <span className="eg-mono text-sm text-[var(--text-muted)]">
                                Loading...
                              </span>
                            ) : events.length === 0 ? (
                              <span className="eg-mono text-sm text-[var(--text-muted)]">
                                No events
                              </span>
                            ) : (
                              <div className="space-y-2">
                                {events.map((ev) => (
                                  <div
                                    key={ev.id}
                                    className="flex items-center gap-4 text-sm"
                                  >
                                    <span className="eg-mono text-[var(--text-muted)]">
                                      #{ev.id}
                                    </span>
                                    <span
                                      className={`eg-badge ${
                                        ev.event_type === "AUTO_RECORDED"
                                          ? "eg-badge-success"
                                          : ev.event_type === "MANUAL_CORRECTION"
                                            ? "eg-badge-warning"
                                            : "eg-badge-neutral"
                                      }`}
                                    >
                                      {ev.event_type}
                                    </span>
                                    <span className="text-[var(--text-secondary)]">
                                      {ev.status_snapshot}
                                    </span>
                                    {ev.recorded_by && (
                                      <span className="text-[var(--text-muted)]">
                                        by {ev.recorded_by}
                                      </span>
                                    )}
                                    <span
                                      className="text-[var(--text-muted)] text-xs"
                                      style={{ fontFamily: "var(--font-mono)" }}
                                    >
                                      {new Date(ev.created_at).toLocaleString()}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="eg-pagination mt-4">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="eg-btn px-3 py-1 disabled:opacity-30"
            >
              Prev
            </button>
            <span className="eg-mono-sm text-[var(--text-muted)]">
              {page} / {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn px-3 py-1 disabled:opacity-30"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
