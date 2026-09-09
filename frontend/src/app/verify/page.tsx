"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiRequest, qs } from "@/lib/api";

interface ExaminationSession {
  id: number;
  exam_id: number;
  exam_hall_id: number;
  status: string;
  gate_status: string;
  started_at: string | null;
}

interface Exam {
  id: number;
  exam_name: string;
  exam_date: string;
  start_time: string;
}

interface ExamHall {
  id: number;
  hall_name: string;
}

interface EntryVerification {
  id: number;
  student_id: number;
  exam_id: number;
  exam_hall_id: number;
  status: string;
  hall_ticket_status: string;
  identity_status: string;
  seat_status: string;
  decision: string | null;
  created_at: string;
}

interface Student {
  id: number;
  usn: string;
  name: string;
}

export default function VerifyPage() {
  const router = useRouter();
  const [activeSession, setActiveSession] = useState<ExaminationSession | null>(null);
  const [sessionExam, setSessionExam] = useState<Exam | null>(null);
  const [sessionHall, setSessionHall] = useState<ExamHall | null>(null);
  const [recentVerifications, setRecentVerifications] = useState<EntryVerification[]>([]);
  const [students, setStudents] = useState<Map<number, Student>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({ verified: 0, rejected: 0, review: 0, pending: 0 });

  const loadActiveSession = useCallback(async () => {
    try {
      const data = await apiRequest<{ items: ExaminationSession[] }>(
        `/api/v1/examination-sessions${qs({ status: "IN_PROGRESS", page_size: 1 })}`
      );
      const session = data.items?.[0];
      if (!session) {
        setLoading(false);
        return;
      }
      setActiveSession(session);

      const [exam, hall] = await Promise.all([
        apiRequest<Exam>(`/api/v1/exams/${session.exam_id}`).catch(() => null),
        apiRequest<ExamHall>(`/api/v1/exam-halls/${session.exam_hall_id}`).catch(() => null),
      ]);
      setSessionExam(exam);
      setSessionHall(hall);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  const loadVerifications = useCallback(async (sessionId: number) => {
    try {
      const data = await apiRequest<{ items: EntryVerification[] }>(
        `/api/v1/entry-verifications${qs({ examination_session_id: sessionId, page_size: 50 })}`
      );
      const items = data.items || [];
      setRecentVerifications(items);

      const s: Student[] = [];
      for (const v of items.slice(0, 20)) {
        if (!students.has(v.student_id)) {
          const student = await apiRequest<Student>(`/api/v1/students/${v.student_id}`).catch(() => null);
          if (student) s.push(student);
        }
      }
      if (s.length > 0) {
        setStudents((prev) => {
          const next = new Map(prev);
          for (const st of s) next.set(st.id, st);
          return next;
        });
      }

      let verified = 0, rejected = 0, review = 0, pending = 0;
      for (const v of items) {
        if (v.status === "PASSED") verified++;
        else if (v.status === "REJECTED") rejected++;
        else if (v.status === "REVIEW") review++;
        else pending++;
      }
      setStats({ verified, rejected, review, pending });
    } catch (err: any) {
      setError(err.message);
    }
  }, [students]);

  useEffect(() => { loadActiveSession(); }, [loadActiveSession]);
  useEffect(() => {
    if (activeSession) {
      loadVerifications(activeSession.id);
      const interval = setInterval(() => loadVerifications(activeSession.id), 10000);
      return () => clearInterval(interval);
    }
  }, [activeSession, loadVerifications]);

  useEffect(() => { setLoading(false); }, []);

  if (loading) return <div className="eg-page"><p style={{ color: "var(--text-muted)" }}>Loading...</p></div>;

  if (!activeSession) {
    return (
      <div className="eg-page">
        <div className="eg-page-header">
          <h1 className="eg-page-title">Verify Entry</h1>
          <p className="eg-page-desc">No active examination session found.</p>
        </div>
        <div className="glass" style={{ padding: "3rem", borderRadius: "var(--radius-lg)", textAlign: "center" }}>
          <p style={{ fontSize: "2rem", marginBottom: "1rem" }}>📋</p>
          <h3 style={{ fontFamily: "var(--font-display)", marginBottom: "0.5rem" }}>No Active Session</h3>
          <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
            Start an examination session to begin verification.
          </p>
          <a href="/examination-sessions" className="eg-btn eg-btn-primary">Go to Sessions</a>
        </div>
      </div>
    );
  }

  return (
    <div className="eg-page">
      {/* Session Header */}
      <div className="glass" style={{ padding: "1.25rem 1.5rem", borderRadius: "var(--radius-lg)", marginBottom: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.25rem" }}>
            <h1 className="eg-page-title" style={{ marginBottom: 0 }}>Verification Console</h1>
            <span className="eg-badge eg-badge-success">ACTIVE</span>
          </div>
          <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
            {sessionExam?.exam_name} · {sessionHall?.hall_name} · Gate: {activeSession.gate_status}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <a href="/monitoring" className="eg-btn eg-btn-sm">Monitor</a>
        </div>
      </div>

      {error && (
        <div className="eg-alert eg-alert-danger" style={{ marginBottom: "1rem" }}>{error}</div>
      )}

      {/* Live Stats */}
      <div className="eg-grid-4" style={{ gap: "1rem", marginBottom: "1.5rem" }}>
        {[
          { label: "Verified", value: stats.verified, color: "var(--success)" },
          { label: "Rejected", value: stats.rejected, color: "var(--danger)" },
          { label: "Review", value: stats.review, color: "var(--warning)" },
          { label: "Pending", value: stats.pending, color: "var(--text-muted)" },
        ].map((item) => (
          <div key={item.label} className="glass" style={{ padding: "1rem", borderRadius: "var(--radius-md)", textAlign: "center" }}>
            <p className="eg-metric-label">{item.label}</p>
            <p className="eg-metric-value" style={{ color: item.color }}>{item.value}</p>
          </div>
        ))}
      </div>

      {/* Recent Verifications */}
      <div className="glass" style={{ borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
        <div style={{ padding: "1rem 1.5rem", borderBottom: "1px solid var(--border)" }}>
          <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1rem" }}>Recent Verifications</h3>
        </div>
        {recentVerifications.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center" }}>
            <p style={{ color: "var(--text-muted)" }}>No verifications yet. Candidates will appear here as they arrive.</p>
          </div>
        ) : (
          <div className="eg-table-wrap" style={{ border: "none", borderRadius: 0, boxShadow: "none" }}>
            <table className="eg-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Student</th>
                  <th>Hall Ticket</th>
                  <th>Identity</th>
                  <th>Seat</th>
                  <th>Status</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {recentVerifications.map((v) => {
                  const student = students.get(v.student_id);
                  const statusColor = v.status === "PASSED" ? "success" : v.status === "REJECTED" ? "danger" : v.status === "REVIEW" ? "warning" : "neutral";
                  return (
                    <tr key={v.id} style={{ cursor: "pointer" }} onClick={() => router.push(`/entry-verifications/${v.id}`)}>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", whiteSpace: "nowrap" }}>
                        {new Date(v.created_at).toLocaleTimeString()}
                      </td>
                      <td>
                        <p style={{ fontWeight: 500, fontSize: "0.875rem" }}>{student?.name || `#${v.student_id}`}</p>
                        <p style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                          {student?.usn || ""}
                        </p>
                      </td>
                      <td>
                        <span className={`eg-badge eg-badge-${v.hall_ticket_status === "PASSED" ? "success" : v.hall_ticket_status === "FAILED" ? "danger" : "neutral"}`} style={{ fontSize: "0.5rem" }}>
                          {v.hall_ticket_status || "PENDING"}
                        </span>
                      </td>
                      <td>
                        <span className={`eg-badge eg-badge-${v.identity_status === "PASSED" ? "success" : v.identity_status === "FAILED" ? "danger" : "neutral"}`} style={{ fontSize: "0.5rem" }}>
                          {v.identity_status || "PENDING"}
                        </span>
                      </td>
                      <td>
                        <span className={`eg-badge eg-badge-${v.seat_status === "PASSED" ? "success" : v.seat_status === "FAILED" ? "danger" : "neutral"}`} style={{ fontSize: "0.5rem" }}>
                          {v.seat_status || "PENDING"}
                        </span>
                      </td>
                      <td>
                        <span className={`eg-badge eg-badge-${statusColor}`}>{v.status}</span>
                      </td>
                      <td style={{ fontWeight: 500, fontSize: "0.875rem" }}>
                        {v.decision || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <a href="/entry-verifications" className="eg-btn">All Verifications</a>
        <a href="/security-events" className="eg-btn">Security Events</a>
        <a href="/security-alerts" className="eg-btn">Alerts</a>
      </div>
    </div>
  );
}
