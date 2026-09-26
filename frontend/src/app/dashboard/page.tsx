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
  uploadDemoReferenceFace,
  assignDemoInvigilator,
  startDemoSession,
  getDemoSessionStatus,
  type DemoStatusResponse,
  type DemoSessionStatus,
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

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const comma = result.indexOf(",");
      const b64 = comma >= 0 ? result.slice(comma + 1) : "";
      if (b64) resolve(b64);
      else reject(new Error("Failed to encode image"));
    };
    reader.onerror = () => reject(new Error("Failed to read image file"));
    reader.readAsDataURL(blob);
  });
}

export default function DashboardPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const { user, isAuthenticated } = useAuth();

  const [demoStatus, setDemoStatus] = useState<DemoStatusResponse | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoMessage, setDemoMessage] = useState("");
  const [demoStudents, setDemoStudents] = useState<DemoStudent[]>([]);
  const [demoLoaded, setDemoLoaded] = useState(false);

  const [invigilatorEmail, setInvigilatorEmail] = useState("");
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignMessage, setAssignMessage] = useState("");

  const [sessionStartLoading, setSessionStartLoading] = useState(false);
  const [sessionMessage, setSessionMessage] = useState("");
  const [sessionStatus, setSessionStatus] = useState<DemoSessionStatus | null>(null);

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

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
        setDemoLoaded(true);
        const names = status.demo_student_names || [];
        const refUrls = status.reference_face_urls || [];
        const students: DemoStudent[] = status.demo_attempt_ids.map((aid, i) => ({
          attempt_id: aid,
          student_id: status.demo_student_ids?.[i] || 0,
          student_usn: status.demo_student_usns?.[i] || `DEMO00${i + 1}`,
          student_name: names[i] || `Demo Candidate ${i + 1}`,
          reference_face_url: refUrls[i] || null,
          file: null,
          preview: null,
          uploading: false,
          uploadMessage: "",
        }));
        setDemoStudents(students);
      } else {
        setDemoLoaded(false);
        setDemoStudents([]);
      }
      try {
        const sess = await getDemoSessionStatus();
        setSessionStatus(sess);
      } catch {
        setSessionStatus(null);
      }
    } catch {
      setDemoLoaded(false);
      setDemoStatus(null);
      setDemoStudents([]);
      setSessionStatus(null);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) refreshDemoState();
  }, [isAuthenticated, refreshDemoState]);

  const handleLoadDemo = async () => {
    setDemoLoading(true);
    setDemoMessage("");
    setSessionMessage("");
    setAssignMessage("");
    try {
      const result = await loadDemoData();
      setDemoMessage(result.message);
      setSelectedExamId(result.demo_exam_id);
      setDemoLoaded(true);
      // Invalidate stale local state: files/previews/messages belong to the
      // previous demo. Refetch authoritative status so the fresh demo shows
      // no previous reference photos and a NOT_STARTED session.
      setSessionStatus(null);
      await refreshDemoState();
    } catch (e: any) {
      setDemoMessage(e.message || "Failed to load demo data");
    } finally {
      setDemoLoading(false);
    }
  };

  const handleResetDemo = async () => {
    setDeleteLoading(true);
    try {
      const result = await resetDemoData();
      setDemoLoaded(false);
      setDemoStatus(null);
      setDemoStudents([]);
      setSessionStatus(null);
      setSelectedExamId(null);
      setDemoMessage(result.message);
      setConfirmDelete(false);
      setInvigilatorEmail("");
      setAssignMessage("");
      setSessionMessage("");
    } catch (e: any) {
      setDemoMessage(e.message || "Failed to delete demo data");
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleRefreshStatus = async () => {
    setDemoLoading(true);
    try {
      await refreshDemoState();
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
      const file = student.file!;
      if (file.size > 5 * 1024 * 1024) {
        throw new Error("Photo is larger than 5MB. Choose a smaller image.");
      }

      let base64: string;
      let imageFormat = file.type || "image/jpeg";
      if (file.size > 3.5 * 1024 * 1024) {
        // Downscale/re-encode large photos so the JSON+base64 body stays under limits.
        const bitmap = await createImageBitmap(file);
        const maxDim = 1600;
        const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(bitmap.width * scale));
        canvas.height = Math.max(1, Math.round(bitmap.height * scale));
        const ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("Failed to process image");
        ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        bitmap.close();
        const jpegBlob = await new Promise<Blob>((resolve, reject) => {
          canvas.toBlob(
            (b) => (b ? resolve(b) : reject(new Error("Failed to compress image"))),
            "image/jpeg",
            0.9
          );
        });
        base64 = await blobToBase64(jpegBlob);
        imageFormat = "image/jpeg";
      } else {
        base64 = await blobToBase64(file);
      }

      const result = await uploadDemoReferenceFace(attemptId, base64, imageFormat);
      const savedUrl = result.reference_face_url;
      if (!savedUrl || !/^https?:\/\//i.test(savedUrl)) {
        throw new Error("Upload did not return a public image URL");
      }

      setDemoStudents((prev) =>
        prev.map((s) =>
          s.attempt_id === attemptId
            ? { ...s, reference_face_url: savedUrl, uploading: false, uploadMessage: "Reference saved" }
            : s
        )
      );
    } catch (e: any) {
      const errorMsg = e.message || "Upload failed";
      setDemoStudents((prev) =>
        prev.map((s) =>
          s.attempt_id === attemptId
            ? { ...s, uploading: false, uploadMessage: errorMsg }
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
      const result = await assignDemoInvigilator(invigilatorEmail);
      setAssignMessage(`Assigned to ${result.email}`);
      try {
        const sess = await getDemoSessionStatus();
        setSessionStatus(sess);
      } catch {}
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
      const result = await startDemoSession(user?.email || "admin");
      setSessionMessage("Session started");
      setSessionStatus((prev) =>
        prev
          ? { ...prev, session_status: result.session_status, gate_status: result.gate_status, loaded: true }
          : {
              loaded: true,
              session_id: result.session_id,
              session_status: result.session_status,
              gate_status: result.gate_status,
              exam_name: null,
              exam_date: null,
              hall_name: null,
              invigilator_email: null,
              started_at: null,
            }
      );
    } catch (e: any) {
      setSessionMessage(e.message || "Failed to start session");
    } finally {
      setSessionStartLoading(false);
    }
  };

  const allEnrolled = demoStudents.length > 0 && demoStudents.every((s) => s.reference_face_url);
  const sessionActive = sessionStatus?.session_status === "IN_PROGRESS";

  const examName = sessionStatus?.exam_name || "ExamGuard Demo Examination";
  const hallName = sessionStatus?.hall_name || "Demo Hall A";

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/" className="eg-breadcrumb">← HOME</Link>
          <h1 className="eg-page-title">Verification Dashboard</h1>
          <p className="eg-page-desc">Exam-level verification status overview</p>
        </div>

        {/* Section 0: Demo Environment - Load / Reload */}
        {!demoLoaded && (
          <div className="glass-surface p-4 mb-6" style={{ borderColor: "rgba(107,78,255,0.2)" }}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="eg-eyebrow" style={{ color: "var(--accent)" }}>Demo Environment</span>
                </div>
                <p className="text-sm text-[var(--text-secondary)]">
                  Load a demonstration scenario with 3 candidates, exam, hall, and session.
                </p>
                {demoMessage && (
                  <p className="text-xs mt-2" style={{ color: "var(--success)" }}>{demoMessage}</p>
                )}
              </div>
              <button onClick={handleLoadDemo} disabled={demoLoading} className="eg-btn eg-btn-primary px-5 py-2 text-sm">
                {demoLoading ? "Loading Demo Data..." : "Load Demo Data"}
              </button>
            </div>
          </div>
        )}

        {/* DEMO PRESENTATION CONTROL CENTER */}
        {demoLoaded && (
          <div className="mb-6">
            {/* ── Section 1: Demo Data Status ── */}
            <div className="glass-surface p-4 mb-4" style={{ borderColor: "rgba(107,78,255,0.2)" }}>
              <div className="flex items-center gap-2 mb-3">
                <span className="eg-eyebrow" style={{ color: "var(--accent)" }}>Demo Presentation Control Center</span>
                {sessionActive && (
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(45,159,111,0.2)", color: "var(--success)" }}>
                    SESSION ACTIVE
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 mb-3">
                <span style={{ color: "var(--success)", fontSize: "0.875rem" }}>✓</span>
                <span className="text-sm font-medium">Demo data loaded</span>
              </div>

              <div className="flex flex-wrap gap-x-6 gap-y-1 mb-4 text-sm">
                <div>
                  <span className="text-[var(--text-muted)]">Exam: </span>
                  <span className="text-[var(--text-secondary)]">{examName}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Hall: </span>
                  <span className="text-[var(--text-secondary)]">{hallName}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Candidates: </span>
                  <span className="text-[var(--text-secondary)]">{demoStudents.length}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Session: </span>
                  {sessionActive ? (
                    <span style={{ color: "var(--success)" }}>IN_PROGRESS</span>
                  ) : (
                    <span style={{ color: "var(--text-muted)" }}>{sessionStatus?.session_status || "NOT_STARTED"}</span>
                  )}
                </div>
              </div>

              {demoMessage && !confirmDelete && (
                <p className="text-xs mb-3" style={{ color: "var(--success)" }}>{demoMessage}</p>
              )}

              <div className="flex items-center gap-3">
                <button onClick={handleRefreshStatus} disabled={demoLoading} className="eg-btn text-xs px-3 py-1.5">
                  {demoLoading ? "Refreshing..." : "Refresh Status"}
                </button>
                {!confirmDelete ? (
                  <button onClick={() => setConfirmDelete(true)} className="eg-btn eg-btn-danger text-xs px-3 py-1.5">
                    Delete Demo Data
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[var(--text-muted)]">Delete Demo Data?</span>
                    <button onClick={handleResetDemo} disabled={deleteLoading} className="eg-btn text-xs px-3 py-1.5" style={{ background: "var(--danger)", color: "#fff" }}>
                      {deleteLoading ? "Deleting..." : "Confirm Delete"}
                    </button>
                    <button onClick={() => setConfirmDelete(false)} className="eg-btn text-xs px-3 py-1.5">
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* ── Section 2: Student Face Enrollment ── */}
            <div className="glass-surface p-4 mb-4" style={{ borderColor: "var(--border)" }}>
              <h2 className="text-base font-semibold mb-1" style={{ fontFamily: "var(--font-display)" }}>
                Student Face Enrollment
              </h2>
              <p className="text-xs text-[var(--text-muted)] mb-4">
                Upload one clear face photo for each demo candidate. Each photo becomes that student&apos;s reference face for live verification.
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1rem" }}>
                {demoStudents.map((student) => (
                  <div
                    key={student.attempt_id}
                    className="p-4 rounded-lg"
                    style={{ border: `1px solid ${student.reference_face_url ? "rgba(45,159,111,0.3)" : "var(--border)"}`, background: "rgba(255,255,255,0.02)" }}
                  >
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
                          REFERENCE NOT ENROLLED
                        </span>
                      )}
                    </div>

                    <div className="flex gap-4">
                      <div style={{ width: "120px", height: "120px", flexShrink: 0, borderRadius: "8px", overflow: "hidden", border: "1px solid var(--border)", aspectRatio: "1 / 1" }}>
                        {student.reference_face_url ? (
                          <img src={student.reference_face_url} alt={student.student_usn} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                        ) : student.preview ? (
                          <img src={student.preview} alt={student.student_usn} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                        ) : (
                          <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.6875rem", textAlign: "center", padding: "0.5rem", lineHeight: 1.3 }}>
                            REFERENCE NOT ENROLLED
                          </div>
                        )}
                      </div>

                      <div className="flex-1 flex flex-col justify-between">
                        <div>
                          <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                            Face Photo
                          </label>
                          <label className="eg-btn text-xs w-full" style={{ cursor: "pointer", textAlign: "center", display: "block" }}>
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
                        {student.file && (
                          <button
                            onClick={() => handleUploadFace(student.attempt_id)}
                            disabled={student.uploading}
                            className="eg-btn eg-btn-primary text-xs mt-2"
                          >
                            {student.uploading
                              ? "Saving..."
                              : student.reference_face_url
                                ? "Replace Reference Face"
                                : "Save Reference Face"}
                          </button>
                        )}
                        {student.uploadMessage && (
                          <p className="text-xs mt-1" style={{ color: student.uploadMessage.includes("saved") || student.uploadMessage.includes("Saved") ? "var(--success)" : "var(--danger)" }}>
                            {student.uploadMessage.includes("saved") || student.uploadMessage.includes("Saved") ? `✓ ${student.uploadMessage}` : student.uploadMessage}
                          </p>
                        )}
                        {student.reference_face_url && (
                          <p className="text-xs mt-1" style={{ color: "var(--success)" }}>✓ Reference saved</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Section 3: Invigilator Assignment ── */}
            <div className="glass-surface p-4 mb-4" style={{ borderColor: "var(--border)" }}>
              <h2 className="text-base font-semibold mb-3" style={{ fontFamily: "var(--font-display)" }}>
                Invigilator Assignment
              </h2>
              <div className="flex flex-wrap items-end gap-3">
                <div style={{ minWidth: "250px", flex: 1 }}>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                    Invigilator Email
                  </label>
                  <input
                    type="email"
                    placeholder="invigilator@example.com"
                    value={invigilatorEmail}
                    onChange={(e) => setInvigilatorEmail(e.target.value)}
                    className="eg-input text-sm w-full"
                  />
                </div>
                <button
                  onClick={handleAssignInvigilator}
                  disabled={!invigilatorEmail || assignLoading}
                  className="eg-btn text-sm"
                >
                  {assignLoading ? "Assigning..." : "Assign Invigilator"}
                </button>
              </div>
              {assignMessage && (
                <p className="text-xs mt-2" style={{ color: assignMessage.startsWith("Assigned") ? "var(--success)" : "var(--danger)" }}>
                  {assignMessage.startsWith("Assigned") ? `✓ ${assignMessage}` : assignMessage}
                </p>
              )}
              {sessionStatus?.invigilator_email && !assignMessage && (
                <p className="text-xs mt-2" style={{ color: "var(--success)" }}>
                  ✓ Assigned to: {sessionStatus.invigilator_email}
                </p>
              )}
            </div>

            {/* ── Section 4: Session Management ── */}
            <div className="glass-surface p-4 mb-4" style={{ borderColor: "var(--border)" }}>
              <h2 className="text-base font-semibold mb-3" style={{ fontFamily: "var(--font-display)" }}>
                Session Management
              </h2>
              <div className="flex flex-wrap gap-x-6 gap-y-1 mb-4 text-sm">
                <div>
                  <span className="text-[var(--text-muted)]">Exam: </span>
                  <span className="text-[var(--text-secondary)]">{examName}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Hall: </span>
                  <span className="text-[var(--text-secondary)]">{hallName}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Status: </span>
                  {sessionActive ? (
                    <span style={{ color: "var(--success)" }}>IN_PROGRESS</span>
                  ) : (
                    <span style={{ color: "var(--text-muted)" }}>{sessionStatus?.session_status || "NOT_STARTED"}</span>
                  )}
                </div>
                {sessionStatus?.invigilator_email && (
                  <div>
                    <span className="text-[var(--text-muted)]">Invigilator: </span>
                    <span className="text-[var(--text-secondary)]">{sessionStatus.invigilator_email}</span>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleStartSession}
                  disabled={sessionStartLoading || sessionActive}
                  className="eg-btn eg-btn-primary text-sm"
                >
                  {sessionStartLoading ? "Starting..." : sessionActive ? "Session Active" : "Start Demo Session"}
                </button>
                {sessionMessage && !sessionActive && (
                  <p className="text-xs" style={{ color: sessionMessage.includes("started") || sessionMessage.includes("active") ? "var(--success)" : "var(--danger)" }}>
                    {sessionMessage}
                  </p>
                )}
                {sessionActive && (
                  <p className="text-xs" style={{ color: "var(--success)" }}>✓ Examination Session Active</p>
                )}
              </div>
            </div>

            {/* ── Section 5: Open Invigilator ── */}
            {sessionActive && (
              <div className="glass-surface p-4 mb-4" style={{ borderColor: "rgba(45,159,111,0.2)" }}>
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold" style={{ fontFamily: "var(--font-display)" }}>
                      Ready for Verification
                    </h2>
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      The session is active. Open the invigilator console on the second computer.
                    </p>
                  </div>
                  <Link href="/invigilator" className="eg-btn eg-btn-primary px-4 py-2 text-sm">
                    Open Invigilator Console →
                  </Link>
                </div>
              </div>
            )}
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
