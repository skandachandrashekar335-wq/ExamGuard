"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  getDemoStatus,
  loadDemoData,
  resetDemoData,
  type DemoStatusResponse,
  type DemoLoadResponse,
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
  student_id: number;
  student_usn: string;
  attempt_id: number;
  attempt_status: string;
  reference_face_url: string | null;
  file: File | null;
  preview: string | null;
  uploading: boolean;
  uploadMessage: string;
}

export default function DashboardPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const { user, isAuthenticated, examGuardToken } = useAuth();

  const [demoStatus, setDemoStatus] = useState<DemoStatusResponse | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoMessage, setDemoMessage] = useState("");
  const [demoStudents, setDemoStudents] = useState<DemoStudent[]>([]);
  const [invigilatorEmail, setInvigilatorEmail] = useState("");
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignMessage, setAssignMessage] = useState("");
  const [sessionStartLoading, setSessionStartLoading] = useState(false);
  const [sessionMessage, setSessionMessage] = useState("");

  useEffect(() => {
    if (!isAuthenticated) return;
    apiRequest<{ items: ExamListItem[] }>("/api/v1/exams?page=1&page_size=100")
      .then((data) => {
        setExams(data.items || []);
      })
      .catch(() => {});
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    getDemoStatus()
      .then(async (status) => {
        setDemoStatus(status);
        if (status.loaded && status.demo_attempt_ids && status.demo_student_usns) {
          const students: DemoStudent[] = status.demo_attempt_ids.map((aid, i) => ({
            student_id: status.demo_student_ids?.[i] || 0,
            student_usn: status.demo_student_usns?.[i] || `DEMO00${i + 1}`,
            attempt_id: aid,
            attempt_status: "CREATED",
            reference_face_url: null,
            file: null,
            preview: null,
            uploading: false,
            uploadMessage: "",
          }));
          setDemoStudents(students);
          for (const s of students) {
            try {
              const ref = await apiRequest<{ reference_face_url: string }>(
                `/api/v1/identity-verifications/${s.attempt_id}/reference-face`
              );
              setDemoStudents((prev) =>
                prev.map((ps) =>
                  ps.attempt_id === s.attempt_id
                    ? { ...ps, reference_face_url: ref.reference_face_url }
                    : ps
                )
              );
            } catch {
              // No reference face yet
            }
          }
        }
      })
      .catch(() => {});
  }, [isAuthenticated]);

  const handleLoadDemo = async () => {
    setDemoLoading(true);
    setDemoMessage("");
    try {
      const result = await loadDemoData();
      setDemoMessage(result.message);
      const status: DemoStatusResponse = {
        loaded: true,
        demo_exam_id: result.demo_exam_id,
        demo_hall_id: result.demo_hall_id,
        demo_student_ids: result.demo_student_ids,
        demo_student_usns: result.demo_student_usns,
        demo_session_id: result.demo_session_id,
        demo_attempt_ids: result.demo_attempt_ids,
      };
      setDemoStatus(status);
      setSelectedExamId(result.demo_exam_id);
      if (result.demo_student_ids && result.demo_student_usns && result.demo_attempt_ids) {
        setDemoStudents(
          result.demo_attempt_ids.map((aid, i) => ({
            student_id: result.demo_student_ids[i],
            student_usn: result.demo_student_usns[i],
            attempt_id: aid,
            attempt_status: "CREATED",
            reference_face_url: null,
            file: null,
            preview: null,
            uploading: false,
            uploadMessage: "",
          }))
        );
      }
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
        s.attempt_id === attemptId ? { ...s, file, preview: url } : s
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
      const reader = new FileReader();
      const base64 = await new Promise<string>((resolve, reject) => {
        reader.onload = () => {
          const result = reader.result as string;
          const b64 = result.split(",")[1];
          if (b64) resolve(b64);
          else reject(new Error("Failed to encode image"));
        };
        reader.onerror = reject;
        reader.readAsDataURL(student.file!);
      });

      await apiRequest(`/api/v1/identity-verifications/${attemptId}/reference-face`, {
        method: "POST",
        body: JSON.stringify({
          reference_image: base64,
          image_format: student.file!.type || "image/jpeg",
        }),
      });

      const ref = await apiRequest<{ reference_face_url: string }>(
        `/api/v1/identity-verifications/${attemptId}/reference-face`
      );

      setDemoStudents((prev) =>
        prev.map((s) =>
          s.attempt_id === attemptId
            ? { ...s, reference_face_url: ref.reference_face_url, uploading: false, uploadMessage: "Reference face saved" }
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
    if (!invigilatorEmail || !demoStatus?.demo_exam_id || !demoStatus?.demo_hall_id) return;
    setAssignLoading(true);
    setAssignMessage("");
    try {
      const userRes = await apiRequest<{ items: { id: number; email: string; role: string }[] }>(
        `/api/v1/users?page_size=100`
      );
      const targetUser = userRes.items?.find(
        (u) => u.email?.toLowerCase() === invigilatorEmail.toLowerCase()
      );
      if (!targetUser) {
        setAssignMessage(
          "User not found. The invigilator must sign in at least once before they can be assigned."
        );
        setAssignLoading(false);
        return;
      }
      await apiRequest("/api/v1/invigilator-assignments", {
        method: "POST",
        body: JSON.stringify({
          user_id: targetUser.id,
          exam_id: demoStatus.demo_exam_id,
          exam_hall_id: demoStatus.demo_hall_id,
          notes: "Assigned via demo workflow",
        }),
      });
      setAssignMessage(`Assigned ${invigilatorEmail} as invigilator`);
    } catch (e: any) {
      setAssignMessage(e.message || "Failed to assign invigilator");
    } finally {
      setAssignLoading(false);
    }
  };

  const handleStartSession = async () => {
    if (!demoStatus?.demo_session_id) return;
    setSessionStartLoading(true);
    setSessionMessage("");
    try {
      await apiRequest(`/api/v1/examination-sessions/${demoStatus.demo_session_id}/start`, {
        method: "POST",
        body: JSON.stringify({ performed_by: user?.email || "admin" }),
      });
      setSessionMessage("Session started successfully");
      setDemoStatus((prev) => (prev ? { ...prev } : prev));
    } catch (e: any) {
      setSessionMessage(e.message || "Failed to start session");
    } finally {
      setSessionStartLoading(false);
    }
  };

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
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                Load a complete ExamGuard demonstration scenario with 3 candidates, exam, hall, session and verification-ready data.
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
                  <div className="text-right hidden sm:block">
                    <div className="text-xs text-[var(--text-muted)]">
                      Exam: <span className="text-[var(--text-secondary)]">ExamGuard Demo Examination</span>
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">
                      Candidates: <span style={{ fontFamily: "var(--font-mono)" }} className="text-[var(--text-secondary)]">DEMO001-003</span>
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">
                      Hall: <span className="text-[var(--text-secondary)]">Demo Hall A</span>
                    </div>
                  </div>
                  <Link
                    href="/invigilator"
                    className="eg-btn eg-btn-primary px-4 py-2 text-sm"
                  >
                    Open Invigilator
                  </Link>
                  <button
                    onClick={handleResetDemo}
                    disabled={demoLoading}
                    className="eg-btn eg-btn-ghost px-3 py-2 text-sm"
                  >
                    {demoLoading ? "..." : "Reset"}
                  </button>
                </>
              ) : (
                <button
                  onClick={handleLoadDemo}
                  disabled={demoLoading}
                  className="eg-btn eg-btn-primary px-5 py-2 text-sm"
                >
                  {demoLoading ? "Loading Demo Data..." : "Load Demo Data"}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Demo Student Face Enrollment */}
        {demoStatus?.loaded && demoStudents.length > 0 && (
          <div className="glass-surface p-4 mb-6" style={{ borderColor: "rgba(107,78,255,0.2)" }}>
            <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>
              Student Face Enrollment
            </h2>
            <p className="text-xs text-[var(--text-muted)] mb-4">
              Upload a face photo for each candidate. The photo is saved to Cloudinary and used as the reference for face verification.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {demoStudents.map((student) => (
                <div key={student.attempt_id} className="p-3 rounded border border-[var(--border)] bg-black/10">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-sm font-medium">{student.student_usn}</span>
                    {student.reference_face_url && (
                      <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(45,159,111,0.2)", color: "var(--success)" }}>
                        ENROLLED
                      </span>
                    )}
                  </div>
                  {student.reference_face_url ? (
                    <img
                      src={student.reference_face_url}
                      alt={`${student.student_usn} reference`}
                      className="w-full h-32 object-cover rounded mb-2 border border-[var(--border)]"
                    />
                  ) : student.preview ? (
                    <img
                      src={student.preview}
                      alt={`${student.student_usn} preview`}
                      className="w-full h-32 object-cover rounded mb-2 border border-[var(--border)]"
                    />
                  ) : (
                    <div className="w-full h-32 rounded mb-2 border border-dashed border-[var(--border)] flex items-center justify-center text-xs text-[var(--text-muted)]">
                      No photo uploaded
                    </div>
                  )}
                  <input
                    type="file"
                    accept="image/jpeg,image/png"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileSelect(student.attempt_id, file);
                    }}
                    className="eg-input text-xs mb-2 w-full"
                  />
                  {student.file && !student.reference_face_url && (
                    <button
                      onClick={() => handleUploadFace(student.attempt_id)}
                      disabled={student.uploading}
                      className="eg-btn eg-btn-primary text-xs w-full py-1"
                    >
                      {student.uploading ? "Uploading..." : "Save Reference Face"}
                    </button>
                  )}
                  {student.uploadMessage && (
                    <p className="text-xs mt-1" style={{ color: student.uploadMessage.includes("saved") ? "var(--success)" : "var(--danger)" }}>
                      {student.uploadMessage}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Session Management */}
        {demoStatus?.loaded && (
          <div className="glass-surface p-4 mb-6" style={{ borderColor: "rgba(107,78,255,0.2)" }}>
            <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>
              Session Management
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Start Session */}
              <div className="p-3 rounded border border-[var(--border)] bg-black/10">
                <h3 className="text-sm font-medium mb-2">Start Examination Session</h3>
                <button
                  onClick={handleStartSession}
                  disabled={sessionStartLoading}
                  className="eg-btn eg-btn-primary text-sm px-4 py-2"
                >
                  {sessionStartLoading ? "Starting..." : "Start Session"}
                </button>
                {sessionMessage && (
                  <p className="text-xs mt-2" style={{ color: sessionMessage.includes("success") ? "var(--success)" : "var(--danger)" }}>
                    {sessionMessage}
                  </p>
                )}
              </div>

              {/* Assign Invigilator */}
              <div className="p-3 rounded border border-[var(--border)] bg-black/10">
                <h3 className="text-sm font-medium mb-2">Assign Invigilator</h3>
                <div className="flex gap-2">
                  <input
                    type="email"
                    placeholder="invigilator@email.com"
                    value={invigilatorEmail}
                    onChange={(e) => setInvigilatorEmail(e.target.value)}
                    className="eg-input text-sm flex-1"
                  />
                  <button
                    onClick={handleAssignInvigilator}
                    disabled={!invigilatorEmail || assignLoading}
                    className="eg-btn eg-btn-primary text-sm px-3 py-1"
                  >
                    {assignLoading ? "..." : "Assign"}
                  </button>
                </div>
                {assignMessage && (
                  <p className="text-xs mt-2" style={{ color: assignMessage.includes("Assigned") ? "var(--success)" : "var(--danger)" }}>
                    {assignMessage}
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
            onChange={(e) => {
              setSelectedExamId(e.target.value ? Number(e.target.value) : null);
            }}
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
