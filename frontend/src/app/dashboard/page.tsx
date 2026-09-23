"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  getDemoStatus,
  loadDemoData,
  resetDemoData,
  type DemoStatusResponse,
} from "@/lib/demo-api";

interface ExamListItem {
  id: number;
  subject_id: number;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  semester: number;
  department: string;
  is_active: boolean;
  subject_code: string | null;
  subject_name: string | null;
}

interface DemoStudent {
  attempt_id: number;
  student_id: number;
  student_usn: string;
  student_name: string;
  reference_face_url: string | null;
  file: File | null;
  preview: string | null;
  uploading: boolean;
  uploadMessage: string;
}

interface SessionStatus {
  loaded: boolean;
  session_id?: number;
  session_status?: string;
  gate_status?: string;
  exam_name?: string;
  exam_date?: string;
  hall_name?: string;
  started_at?: string;
}

export default function DashboardPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const { user, isAuthenticated } = useAuth();

  const [demoStatus, setDemoStatus] = useState<DemoStatusResponse | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoMessage, setDemoMessage] = useState("");
  const [demoStudents, setDemoStudents] = useState<DemoStudent[]>([]);

  const [invigilatorEmail, setInvigilatorEmail] = useState("");
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignMessage, setAssignMessage] = useState("");

  const [sessionStartLoading, setSessionStartLoading] = useState(false);
  const [sessionMessage, setSessionMessage] = useState("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    apiRequest<{ items: ExamListItem[] }>("/api/v1/exams?page=1&page_size=100")
      .then((data) => setExams(data.items || []))
      .catch(() => {});
  }, [isAuthenticated]);

  const refreshDemoState = useCallback(async () => {
    try {
      const status = await getDemoStatus();
      setDemoStatus(status);
      if (status.loaded && status.demo_attempt_ids && status.demo_student_usns) {
        const students: DemoStudent[] = await Promise.all(
          status.demo_attempt_ids.map(async (aid, i) => {
            let refUrl: string | null = null;
            try {
              const ref = await apiRequest<{ reference_face_url: string }>(
                `/api/v1/identity-verifications/${aid}/reference-face`
              );
              refUrl = ref.reference_face_url;
            } catch {
              // No reference face yet
            }
            return {
              attempt_id: aid,
              student_id: status.demo_student_ids?.[i] || 0,
              student_usn: status.demo_student_usns?.[i] || `DEMO00${i + 1}`,
              student_name: `Demo Candidate ${i + 1}`,
              reference_face_url: refUrl,
              file: null,
              preview: null,
              uploading: false,
              uploadMessage: "",
            };
          })
        );
        setDemoStudents(students);
      }
      try {
        const sess = await apiRequest<SessionStatus>("/api/v1/demo/session-status");
        setSessionStatus(sess);
      } catch {
        setSessionStatus(null);
      }
    } catch {
      setDemoStatus(null);
      setDemoStudents([]);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) refreshDemoState();
  }, [isAuthenticated, refreshDemoState]);

  const handleLoadDemo = async () => {
    setDemoLoading(true);
    setDemoMessage("");
    try {
      const result = await loadDemoData();
      setDemoMessage(result.message);
      setSelectedExamId(result.demo_exam_id);
      await refreshDemoState();
    } catch (e: any) {
      setDemoMessage(e.message || "Failed to load demo data");
    } finally {
      setDemoLoading(false);
    }
  };

  const handleResetDemo = async () => {
    if (!window.confirm("Reset Demo Data?\n\nThis removes only ExamGuard demonstration records.")) return;
    setDemoLoading(true);
    setDemoMessage("");
    try {
      const result = await resetDemoData();
      setDemoMessage(result.message);
      setDemoStatus(null);
      setDemoStudents([]);
      setSessionStatus(null);
    } catch (e: any) {
      setDemoMessage(e.message || "Failed to reset demo data");
    } finally {
      setDemoLoading(false);
    }
  };

  const handleFileSelect = (attemptId: number, file: File) => {
    const url = URL.createObjectURL(file);
    setDemoStudents((prev) =>
      prev.map((s) =>
        s.attempt_id === attemptId ? { ...s, file, preview: url, uploadMessage: "" } : s
      )
    );
  };

  const handleUploadFace = async (attemptId: number) => {
    const student = demoStudents.find((s) => s.attempt_id === attemptId);
    if (!student?.file) return;

    setDemoStudents((prev) =>
      prev.map((s) => (s.attempt_id === attemptId ? { ...s, uploading: true, uploadMessage: "" } : s))
    );

    try {
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = reader.result as string;
          const b64 = result.split(",")[1];
          if (b64) resolve(b64);
          else reject(new Error("Failed to encode image"));
        };
        reader.onerror = reject;
        reader.readAsDataURL(student.file!);
      });

      const result = await apiRequest<{ status: string; reference_face_url: string }>(
        "/api/v1/demo/upload-reference-face",
        {
          method: "POST",
          body: JSON.stringify({
            attempt_id: attemptId,
            reference_image: base64,
            image_format: student.file!.type || "image/jpeg",
          }),
        }
      );

      setDemoStudents((prev) =>
        prev.map((s) =>
          s.attempt_id === attemptId
            ? { ...s, reference_face_url: result.reference_face_url, uploading: false, uploadMessage: "Saved" }
            : s
        )
      );
    } catch (e: any) {
      setDemoStudents((prev) =>
        prev.map((s) =>
          s.attempt_id === attemptId
            ? { ...s, uploading: false, uploadMessage: e.message || "Upload failed" }
            : s
        )
      );
    }
  };

  const handleAssignInvigilator = async () => {
    if (!invigilatorEmail) return;
    setAssignLoading(true);
    setAssignMessage("");
    try {
      const result = await apiRequest<{ status: string; email: string }>(
        "/api/v1/demo/assign-invigilator",
        {
          method: "POST",
          body: JSON.stringify({ email: invigilatorEmail }),
        }
      );
      setAssignMessage(`Assigned ${result.email}`);
    } catch (e: any) {
      setAssignMessage(e.message || "Failed to assign invigilator");
    } finally {
      setAssignLoading(false);
    }
  };

  const handleStartSession = async () => {
    setSessionStartLoading(true);
    setSessionMessage("");
    try {
      const result = await apiRequest<{ status: string; session_id: number; session_status: string }>(
        "/api/v1/demo/start-session",
        { method: "POST", body: JSON.stringify({ performed_by: user?.email || "admin" }) }
      );
      setSessionMessage("Session active");
      setSessionStatus({
        loaded: true,
        session_id: result.session_id,
        session_status: result.session_status,
      });
    } catch (e: any) {
      setSessionMessage(e.message || "Failed to start session");
    } finally {
      setSessionStartLoading(false);
    }
  };

  const allEnrolled = demoStudents.length > 0 && demoStudents.every((s) => s.reference_face_url);
  const sessionActive = sessionStatus?.session_status === "IN_PROGRESS";

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/" className="eg-breadcrumb">← HOME</Link>
          <h1 className="eg-page-title">Verification Dashboard</h1>
          <p className="eg-page-desc">Exam-level verification status overview</p>
        </div>

        {/* Demo Environment Card */}
        <div className="glass-surface p-4 mb-6" style={{ borderColor: "rgba(107,78,255,0.2)" }}>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="eg-eyebrow" style={{ color: "var(--accent)" }}>Demo Environment</span>
                {sessionActive && (
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(45,159,111,0.2)", color: "var(--success)" }}>
                    SESSION ACTIVE
                  </span>
                )}
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                {demoStatus?.loaded
                  ? "Demo scenario loaded. Enroll student faces, assign invigilator, and start the session."
                  : "Load a demonstration scenario with 3 candidates, exam, hall, and session."}
              </p>
              {demoMessage && (
                <p className="text-xs mt-2" style={{ color: demoMessage.includes("success") || demoMessage.includes("ready") ? "var(--success)" : "var(--text-muted)" }}>
                  {demoMessage}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {demoStatus?.loaded ? (
                <>
                  <Link href="/invigilator" className="eg-btn eg-btn-primary px-4 py-2 text-sm">
                    Open Invigilator
                  </Link>
                  <button onClick={handleResetDemo} disabled={demoLoading} className="eg-btn eg-btn-ghost px-3 py-2 text-sm">
                    {demoLoading ? "..." : "Reset"}
                  </button>
                </>
              ) : (
                <button onClick={handleLoadDemo} disabled={demoLoading} className="eg-btn eg-btn-primary px-5 py-2 text-sm">
                  {demoLoading ? "Loading Demo Data..." : "Load Demo Data"}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Student Face Enrollment Cards */}
        {demoStatus?.loaded && demoStudents.length > 0 && (
          <div className="mb-6">
            <h2 className="text-lg font-semibold mb-3" style={{ fontFamily: "var(--font-display)" }}>
              Student Face Enrollment
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
              {demoStudents.map((student) => (
                <div
                  key={student.attempt_id}
                  className="glass-surface p-4"
                  style={{ borderColor: student.reference_face_url ? "rgba(45,159,111,0.3)" : "var(--border)" }}
                >
                  {/* Header */}
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <span className="font-mono text-sm font-semibold">{student.student_usn}</span>
                      <span className="text-xs text-[var(--text-muted)] ml-2">{student.student_name}</span>
                    </div>
                    {student.reference_face_url ? (
                      <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(45,159,111,0.2)", color: "var(--success)" }}>
                        ENROLLED
                      </span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.05)", color: "var(--text-muted)" }}>
                        PENDING
                      </span>
                    )}
                  </div>

                  {/* Face preview + controls */}
                  <div className="flex gap-4">
                    {/* Image preview - constrained */}
                    <div style={{ width: "120px", height: "120px", flexShrink: 0, borderRadius: "8px", overflow: "hidden", border: "1px solid var(--border)" }}>
                      {student.reference_face_url ? (
                        <img src={student.reference_face_url} alt={student.student_usn} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      ) : student.preview ? (
                        <img src={student.preview} alt={student.student_usn} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      ) : (
                        <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                          No photo
                        </div>
                      )}
                    </div>

                    {/* Controls */}
                    <div className="flex-1 flex flex-col justify-between">
                      <div>
                        <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                          Face Photo
                        </label>
                        <label
                          className="eg-btn text-xs w-full"
                          style={{ cursor: "pointer", textAlign: "center", display: "block" }}
                        >
                          {student.file ? student.file.name : student.reference_face_url ? "Change Photo" : "Choose Photo"}
                          <input
                            type="file"
                            accept="image/jpeg,image/png"
                            style={{ display: "none" }}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) handleFileSelect(student.attempt_id, file);
                            }}
                          />
                        </label>
                      </div>

                      {student.file && !student.reference_face_url && (
                        <button
                          onClick={() => handleUploadFace(student.attempt_id)}
                          disabled={student.uploading}
                          className="eg-btn eg-btn-primary text-xs mt-2"
                        >
                          {student.uploading ? "Saving..." : "Save Reference"}
                        </button>
                      )}

                      {student.uploadMessage && (
                        <p className="text-xs mt-1" style={{ color: student.uploadMessage === "Saved" ? "var(--success)" : "var(--danger)" }}>
                          {student.uploadMessage}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Session Management */}
        {demoStatus?.loaded && (
          <div className="glass-surface p-4 mb-6" style={{ borderColor: "rgba(107,78,255,0.2)" }}>
            <h2 className="text-lg font-semibold mb-3" style={{ fontFamily: "var(--font-display)" }}>
              Session Management
            </h2>

            {/* Session status */}
            {sessionStatus?.loaded && (
              <div className="flex flex-wrap items-center gap-3 mb-4 p-3 rounded" style={{ background: "rgba(255,255,255,0.03)" }}>
                <div className="text-sm">
                  <span className="text-[var(--text-muted)]">Exam: </span>
                  <span className="text-[var(--text-secondary)]">{sessionStatus.exam_name || "ExamGuard Demo Examination"}</span>
                </div>
                <div className="text-sm">
                  <span className="text-[var(--text-muted)]">Hall: </span>
                  <span className="text-[var(--text-secondary)]">{sessionStatus.hall_name || "Demo Hall A"}</span>
                </div>
                <div className="text-sm">
                  <span className="text-[var(--text-muted)]">Status: </span>
                  {sessionActive ? (
                    <span style={{ color: "var(--success)" }}>IN_PROGRESS</span>
                  ) : (
                    <span style={{ color: "var(--text-muted)" }}>{sessionStatus.session_status || "NOT_STARTED"}</span>
                  )}
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-4">
              {/* Assign invigilator */}
              <div className="flex-1" style={{ minWidth: "250px" }}>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  Invigilator Email
                </label>
                <div className="flex gap-2">
                  <input
                    type="email"
                    placeholder="invigilator@example.com"
                    value={invigilatorEmail}
                    onChange={(e) => setInvigilatorEmail(e.target.value)}
                    className="eg-input text-sm flex-1"
                  />
                  <button
                    onClick={handleAssignInvigilator}
                    disabled={!invigilatorEmail || assignLoading}
                    className="eg-btn text-sm"
                  >
                    {assignLoading ? "..." : "Assign"}
                  </button>
                </div>
                {assignMessage && (
                  <p className="text-xs mt-1" style={{ color: assignMessage.startsWith("Assigned") ? "var(--success)" : "var(--danger)" }}>
                    {assignMessage}
                  </p>
                )}
              </div>

              {/* Start session */}
              <div style={{ minWidth: "180px" }}>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  &nbsp;
                </label>
                <button
                  onClick={handleStartSession}
                  disabled={sessionStartLoading || sessionActive}
                  className="eg-btn eg-btn-primary text-sm w-full"
                >
                  {sessionStartLoading ? "Starting..." : sessionActive ? "Session Active" : "Start Session"}
                </button>
                {sessionMessage && !sessionActive && (
                  <p className="text-xs mt-1" style={{ color: sessionMessage.includes("active") ? "var(--success)" : "var(--danger)" }}>
                    {sessionMessage}
                  </p>
                )}
              </div>
            </div>

            <div className="mt-4 flex gap-3">
              <Link href="/examination-sessions" className="eg-btn text-xs">Sessions →</Link>
              <Link href="/invigilator" className="eg-btn text-xs">Invigilator →</Link>
            </div>
          </div>
        )}

        {/* Navigation Links */}
        <div className="eg-filter-bar mb-6">
          <Link href="/monitoring" className="eg-btn text-xs">Monitoring →</Link>
          <Link href="/examination-sessions" className="eg-btn text-xs">Sessions →</Link>
          <Link href="/security-events" className="eg-btn text-xs">Security Events →</Link>
          <Link href="/security-alerts" className="eg-btn text-xs">Security Alerts →</Link>
        </div>

        {/* Exam selector */}
        <div className="mb-6">
          <select
            value={selectedExamId ?? ""}
            onChange={(e) => setSelectedExamId(e.target.value ? Number(e.target.value) : null)}
            className="eg-select w-full max-w-lg"
          >
            <option value="">Select an exam...</option>
            {exams.map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.exam_name} — {ex.exam_date} ({ex.subject_code || "N/A"})
              </option>
            ))}
          </select>
        </div>
      </div>
    </AppShell>
  );
}
