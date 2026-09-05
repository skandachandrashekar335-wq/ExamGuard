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

const STATUS_CLASSES: Record<string, string> = {
  PRESENT: "border-white/40 text-white",
  ABSENT: "border-white/20 text-[var(--text-secondary)]",
  EXCUSED: "border-white/30 text-white",
  NOT_RECORDED: "border-white/10 text-[var(--text-muted)]",
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
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <Link
            href="/attendance"
            className="eg-mono-sm text-[var(--text-muted)] hover:text-white transition-colors"
          >
            ← Attendance
          </Link>
        </div>

        <h1 className="eg-display text-3xl mb-2">Exam Attendance</h1>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Exam #{examId}
        </p>

        {summary && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-6 mb-8">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-6">
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Registered
                </div>
                <div className="eg-display text-2xl">
                  {summary.total_registered}
                </div>
              </div>
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Present
                </div>
                <div className="eg-display text-2xl">
                  {summary.total_present}
                </div>
              </div>
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Absent
                </div>
                <div className="eg-display text-2xl">
                  {summary.total_absent}
                </div>
              </div>
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Excused
                </div>
                <div className="eg-display text-2xl">
                  {summary.total_excused}
                </div>
              </div>
              <div>
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-1">
                  Rate
                </div>
                <div className="eg-display text-2xl">
                  {Math.round(summary.attendance_rate)}%
                </div>
              </div>
            </div>

            {summary.by_hall.length > 0 && (
              <div className="mt-6 border-t border-white/10 pt-4">
                <div className="eg-mono text-xs text-[var(--text-muted)] mb-3">
                  By Hall
                </div>
                <div className="flex flex-wrap gap-4">
                  {summary.by_hall.map((h) => (
                    <div
                      key={h.hall_id}
                      className="border border-white/10 px-4 py-2 text-sm"
                    >
                      <span className="text-white">{h.hall_name}</span>
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

        <div className="flex flex-wrap gap-3 mb-6">
          <input
            type="text"
            placeholder="Hall ID..."
            value={hallFilter}
            onChange={(e) => {
              setHallFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30 w-32"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:border-white/30"
          >
            <option value="">All statuses</option>
            <option value="PRESENT">Present</option>
            <option value="ABSENT">Absent</option>
            <option value="EXCUSED">Excused</option>
            <option value="NOT_RECORDED">Not Recorded</option>
          </select>
        </div>

        {error && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-4 mb-6">
            <span className="eg-mono text-red-400">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">
              Loading attendance records...
            </span>
          </div>
        ) : records.length === 0 ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <h3 className="eg-mono text-[var(--text-secondary)] mb-2">
              No records
            </h3>
            <p className="text-sm text-[var(--text-muted)]">
              No attendance records found for this exam.
            </p>
          </div>
        ) : (
          <div className="border border-white/10 bg-[var(--bg-raised)] overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    ID
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Student
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Hall
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Seat
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Method
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Entry Time
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    EV
                  </th>
                  <th className="px-4 py-3 text-right eg-mono-sm text-[var(--text-muted)]">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <Fragment key={r.id}>
                    <tr
                      className="border-b border-white/5 hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-sm">{r.id}</td>
                      <td className="px-4 py-3 text-sm">#{r.student_id}</td>
                      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                        #{r.hall_id}
                      </td>
                      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                        {r.seat_number ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-[10px] eg-mono border px-2 py-0.5 ${
                            STATUS_CLASSES[r.status] ||
                            "border-white/10 text-[var(--text-muted)]"
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono">
                        {r.entry_method}
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono">
                        {new Date(r.entry_time).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => loadEvents(r.entry_verification_id)}
                          className="eg-mono-sm text-white hover:text-[var(--text-secondary)] transition-colors"
                        >
                          #{r.entry_verification_id}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() =>
                            setShowCorrect(showCorrect === r.id ? null : r.id)
                          }
                          className="eg-mono-sm text-white hover:text-[var(--text-secondary)] transition-colors"
                        >
                          Correct
                        </button>
                      </td>
                    </tr>
                    {showCorrect === r.id && (
                      <tr key={`${r.id}-correct`} className="border-b border-white/5">
                        <td colSpan={9} className="px-4 py-4 bg-[var(--bg-base)]">
                          <div className="border border-white/10 p-4">
                            <h4 className="eg-mono text-sm text-[var(--text-secondary)] mb-3">
                              Manual Correction — Student #{r.student_id}
                            </h4>
                            {correctError && (
                              <div className="border border-white/10 bg-[var(--bg-raised)] p-3 mb-3">
                                <span className="eg-mono text-sm text-red-400">
                                  {correctError}
                                </span>
                              </div>
                            )}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                              <div>
                                <label className="block eg-mono-sm text-[var(--text-muted)] mb-1">
                                  Status
                                </label>
                                <select
                                  value={correctStatus}
                                  onChange={(e) =>
                                    setCorrectStatus(e.target.value)
                                  }
                                  className="w-full bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:border-white/30"
                                >
                                  <option value="EXCUSED">EXCUSED</option>
                                  <option value="PRESENT">PRESENT</option>
                                </select>
                              </div>
                              <div>
                                <label className="block eg-mono-sm text-[var(--text-muted)] mb-1">
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
                                  className="w-full bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30"
                                />
                              </div>
                              <div>
                                <label className="block eg-mono-sm text-[var(--text-muted)] mb-1">
                                  Corrected By *
                                </label>
                                <input
                                  type="text"
                                  required
                                  value={correctBy}
                                  onChange={(e) => setCorrectBy(e.target.value)}
                                  placeholder="Admin ID"
                                  className="w-full bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30"
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
                                className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
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
                        className="border-b border-white/5"
                      >
                        <td colSpan={9} className="px-4 py-4 bg-[var(--bg-base)]">
                          <div className="border border-white/10 p-4">
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="eg-mono text-sm text-[var(--text-secondary)]">
                                Events for EV #{r.entry_verification_id}
                              </h4>
                              <Link
                                href={`/attendance/events/${r.entry_verification_id}`}
                                className="eg-mono-sm text-white hover:text-[var(--text-secondary)] transition-colors"
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
                                      className={`text-[10px] eg-mono border px-2 py-0.5 ${
                                        ev.event_type === "AUTO_RECORDED"
                                          ? "border-white/30 text-white"
                                          : ev.event_type === "MANUAL_CORRECTION"
                                            ? "border-white/20 text-[var(--text-secondary)]"
                                            : "border-white/10 text-[var(--text-muted)]"
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
                                    <span className="text-[var(--text-muted)] font-mono text-xs">
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
          <div className="flex items-center justify-between mt-4">
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
    </div>
  );
}
