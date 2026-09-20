"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getInvigilatorDashboard,
  startExam,
  endExam,
  type InvigilatorDashboard,
} from "@/lib/invigilator-api";
import { apiRequest } from "@/lib/api";
import { ApiError } from "@/lib/api";
import { listAttempts, getAttemptContext, verifyFace, evaluateEvidence, ApiError as IvApiError } from "@/lib/iv-api";
import type { VerificationContext } from "@/lib/types";
import CameraCapture from "@/components/CameraCapture";
import EvidenceDisplay from "@/components/EvidenceDisplay";
import DecisionDisplay from "@/components/DecisionDisplay";
import AppShell from "@/components/AppShell";

function fileToBase64(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1];
      if (base64) resolve(base64);
      else reject(new Error("Failed to encode image"));
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function InvigilatorPage() {
  const [data, setData] = useState<InvigilatorDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // Registered students state
  interface RegisteredStudent {
    registration_id: number;
    student_id: number;
    student_usn: string;
    student_name: string;
    attempt_id: number | null;
    attempt_status: string | null;
    attempt_decision: string | null;
    reference_face_url: string | null;
  }
  const [students, setStudents] = useState<RegisteredStudent[]>([]);

  // Face verification state
  const [verifyStudentId, setVerifyStudentId] = useState<number | null>(null);
  const [verifyAttemptId, setVerifyAttemptId] = useState<number | null>(null);
  const [verifyCtx, setVerifyCtx] = useState<VerificationContext | null>(null);
  const [probeImage, setProbeImage] = useState<Blob | null>(null);
  const [verifyState, setVerifyState] = useState<"idle" | "capturing" | "verifying" | "done" | "error">("idle");
  const [verifyResult, setVerifyResult] = useState<{ decision: string; evidence: unknown[] } | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const dash = await getInvigilatorDashboard();
      setData(dash);
      // Fetch registered students for this invigilator's exam
      try {
        const studentsRes = await apiRequest<{ items: RegisteredStudent[]; total: number }>(
          `/api/v1/invigilator/registered-students`
        );
        setStudents(studentsRes.items || []);
      } catch {
        setStudents([]);
      }
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to load dashboard";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleStart = async () => {
    try {
      setActionLoading(true);
      setActionMsg(null);
      const res = await startExam();
      setActionMsg(`Exam started. Session ${res.session_id}`);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to start exam";
      setActionMsg(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleEnd = async () => {
    try {
      setActionLoading(true);
      setActionMsg(null);
      const res = await endExam();
      setActionMsg(`Exam ended. Session ${res.session_id}`);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to end exam";
      setActionMsg(msg);
    } finally {
      setActionLoading(false);
    }
  };

  // Face verification flow
  const handleStartVerify = async (studentId: number, attemptId: number) => {
    setVerifyStudentId(studentId);
    setVerifyAttemptId(attemptId);
    setVerifyState("capturing");
    setVerifyResult(null);
    setVerifyError(null);
    setProbeImage(null);
    try {
      const ctx = await getAttemptContext(attemptId);
      setVerifyCtx(ctx);
    } catch {
      setVerifyError("Failed to load attempt context");
      setVerifyState("error");
    }
  };

  const handleCapture = (blob: Blob) => {
    setProbeImage(blob);
  };

  const handleVerifyNow = async () => {
    if (!probeImage || !verifyAttemptId) return;
    setVerifyState("verifying");
    setVerifyError(null);
    try {
      const probeBase64 = await fileToBase64(probeImage);
      await verifyFace(verifyAttemptId, {
        probe_image: probeBase64,
        probe_image_format: probeImage.type || "image/jpeg",
      });
      await evaluateEvidence(verifyAttemptId);
      const updated = await getAttemptContext(verifyAttemptId);
      setVerifyCtx(updated);
      setVerifyResult({
        decision: updated.attempt.decision,
        evidence: updated.evidence,
      });
      setVerifyState("done");
      await load();
    } catch (e: unknown) {
      const msg = e instanceof IvApiError ? e.message : "Verification failed";
      setVerifyError(msg);
      setVerifyState("error");
    }
  };

  const handleCloseVerify = () => {
    setVerifyStudentId(null);
    setVerifyAttemptId(null);
    setVerifyCtx(null);
    setProbeImage(null);
    setVerifyState("idle");
    setVerifyResult(null);
    setVerifyError(null);
  };

  if (loading) return <AppShell><div className="p-8 text-center text-lg">Loading invigilator dashboard...</div></AppShell>;
  if (error) return <AppShell><div className="p-8 text-center text-red-600">Error: {error}</div></AppShell>;
  if (!data) return <AppShell><div className="p-8 text-center">No data</div></AppShell>;

  const { profile: p } = data;

  return (
    <AppShell>
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Invigilator Control Center</h1>

      {/* Profile card */}
      <div className="eg-panel p-4 space-y-2">
        <div className="text-sm opacity-60">Logged in as</div>
        <div className="font-medium">{p.full_name || p.email}</div>
        <div className="text-sm opacity-60">{p.email}</div>
      </div>

      {/* Exam info */}
      <div className="eg-panel p-4 space-y-3">
        <h2 className="text-lg font-semibold">Assigned Examination</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><span className="opacity-60">Exam:</span> {p.exam_name}</div>
          <div><span className="opacity-60">Subject:</span> {p.subject_code} — {p.subject_name}</div>
          <div><span className="opacity-60">Date:</span> {p.exam_date}</div>
          <div><span className="opacity-60">Time:</span> {p.exam_start_time} — {p.exam_end_time}</div>
          <div><span className="opacity-60">Hall:</span> {p.hall_name} ({p.hall_building} {p.hall_room})</div>
          <div><span className="opacity-60">Entry Point:</span> {p.entry_point_name || "Not assigned"} ({p.entry_point_code || "N/A"})</div>
          <div><span className="opacity-60">Camera:</span> {p.camera_name || "Not assigned"} ({p.camera_status || "N/A"})</div>
          <div><span className="opacity-60">Session Status:</span> {p.session_status || "No session"}</div>
          <div><span className="opacity-60">Gate Status:</span> {p.gate_status || "N/A"}</div>
        </div>
      </div>

      {/* Controls */}
      <div className="eg-panel p-4 space-y-3">
        <h2 className="text-lg font-semibold">Session Controls</h2>
        <div className="flex gap-3">
          <button
            onClick={handleStart}
            disabled={!data.can_start || actionLoading}
            className="px-4 py-2 rounded bg-green-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {actionLoading ? "Starting..." : "Start Exam"}
          </button>
          <button
            onClick={handleEnd}
            disabled={!data.can_end || actionLoading}
            className="px-4 py-2 rounded bg-red-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {actionLoading ? "Ending..." : "End Exam"}
          </button>
          <button
            onClick={load}
            disabled={actionLoading}
            className="px-4 py-2 rounded border border-[var(--border)]"
          >
            Refresh
          </button>
        </div>
        {actionMsg && <div className="text-sm mt-2 p-2 rounded bg-black/20">{actionMsg}</div>}
        {!data.can_start && !data.can_end && p.session_status !== "IN_PROGRESS" && (
          <div className="text-sm opacity-60">
            Exam is not within the permitted start window. Start is allowed 15 minutes before the scheduled time.
          </div>
        )}
      </div>

      {/* Live stats */}
      <div className="eg-panel p-4 space-y-3">
        <h2 className="text-lg font-semibold">Live Statistics</h2>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="p-3 rounded bg-green-500/10">
            <div className="text-2xl font-bold text-green-400">{data.granted_count}</div>
            <div className="text-xs opacity-60">Verified</div>
          </div>
          <div className="p-3 rounded bg-red-500/10">
            <div className="text-2xl font-bold text-red-400">{data.denied_count}</div>
            <div className="text-xs opacity-60">Denied</div>
          </div>
          <div className="p-3 rounded bg-yellow-500/10">
            <div className="text-2xl font-bold text-yellow-400">{data.escalated_count}</div>
            <div className="text-xs opacity-60">Review</div>
          </div>
          <div className="p-3 rounded bg-blue-500/10">
            <div className="text-2xl font-bold text-blue-400">{data.attendance_count}</div>
            <div className="text-xs opacity-60">Attendance</div>
          </div>
          <div className="p-3 rounded bg-orange-500/10">
            <div className="text-2xl font-bold text-orange-400">{data.security_event_count}</div>
            <div className="text-xs opacity-60">Security Events</div>
          </div>
          <div className="p-3 rounded bg-white/5">
            <div className="text-2xl font-bold">{data.verification_count}</div>
            <div className="text-xs opacity-60">Total Verifications</div>
          </div>
        </div>
      </div>

      {/* Recent verifications */}
      {data.recent_verifications.length > 0 && (
        <div className="eg-panel p-4 space-y-3">
          <h2 className="text-lg font-semibold">Recent Verifications</h2>
          <div className="space-y-2">
            {data.recent_verifications.map((v: Record<string, unknown>) => (
              <div key={v.id as number} className="flex items-center gap-3 text-sm p-2 rounded bg-black/10">
                <span className="font-mono text-xs opacity-50">#{v.id as number}</span>
                <span className="opacity-60">Student {v.student_id as number}</span>
                <span className={`px-2 py-0.5 rounded text-xs ${
                  v.status === "GRANTED" ? "bg-green-500/20 text-green-300" :
                  v.status === "DENIED" ? "bg-red-500/20 text-red-300" :
                  "bg-yellow-500/20 text-yellow-300"
                }`}>
                  {v.status as string}
                </span>
                <span className="text-xs opacity-40">{v.created_at as string}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Registered Students */}
      <div className="eg-panel p-4 space-y-3">
        <h2 className="text-lg font-semibold">Registered Students</h2>
        {students.length === 0 ? (
          <div className="text-sm opacity-60">No registered students found.</div>
        ) : (
          <div className="space-y-2">
            {students.map((s) => (
              <div key={s.registration_id} className="flex items-center justify-between text-sm p-3 rounded bg-black/10">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs opacity-50">{s.student_usn}</span>
                  <span className="font-medium">{s.student_name}</span>
                  {s.attempt_status && (
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      s.attempt_decision === "MATCH" ? "bg-green-500/20 text-green-300" :
                      s.attempt_decision === "NO_MATCH" ? "bg-red-500/20 text-red-300" :
                      "bg-yellow-500/20 text-yellow-300"
                    }`}>
                      {s.attempt_status} / {s.attempt_decision || "PENDING"}
                    </span>
                  )}
                  {s.reference_face_url && (
                    <span className="text-xs text-[var(--accent)]">Reference enrolled</span>
                  )}
                </div>
                {s.attempt_id && (
                  <button
                    onClick={() => handleStartVerify(s.student_id, s.attempt_id!)}
                    className="eg-btn eg-btn-primary text-xs px-3 py-1"
                  >
                    Verify Face
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Face Verification Modal */}
      {verifyAttemptId && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="glass-surface max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Face Verification</h3>
              <button onClick={handleCloseVerify} className="text-[var(--text-muted)] hover:text-white text-xl">&times;</button>
            </div>

            {verifyCtx?.student && (
              <div className="text-sm opacity-60">
                Student: {verifyCtx.student.name} ({verifyCtx.student.usn})
              </div>
            )}

            {/* Reference face display */}
            {verifyCtx?.attempt?.reference_face_url && (
              <div className="space-y-1">
                <span className="eg-mono-sm text-[var(--text-muted)]">Stored Reference</span>
                <img
                  src={verifyCtx.attempt.reference_face_url}
                  alt="Reference face"
                  className="w-48 h-36 object-cover rounded border border-[var(--border)]"
                />
              </div>
            )}

            {/* Camera capture */}
            {verifyState === "capturing" && (
              <div className="space-y-3">
                <span className="eg-mono-sm text-[var(--text-muted)]">CAPTURE PROBE IMAGE</span>
                <CameraCapture
                  onCapture={(blob) => handleCapture(blob)}
                  onRetake={() => setProbeImage(null)}
                />
                {probeImage && (
                  <div className="flex gap-3">
                    <button
                      onClick={handleVerifyNow}
                      className="eg-btn eg-btn-primary px-6 py-2"
                    >
                      Verify Now
                    </button>
                    <button
                      onClick={() => setProbeImage(null)}
                      className="eg-btn px-4 py-2"
                    >
                      Retake
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Verifying state */}
            {verifyState === "verifying" && (
              <div className="text-center py-8">
                <div className="text-lg animate-pulse">Verifying identity...</div>
              </div>
            )}

            {/* Result */}
            {verifyState === "done" && verifyResult && (
              <div className="space-y-3">
                <DecisionDisplay
                  decision={verifyResult.decision}
                  failureReason={verifyCtx?.attempt?.failure_reason || null}
                />
                {verifyResult.evidence.length > 0 && (
                  <EvidenceDisplay evidence={verifyResult.evidence as VerificationContext["evidence"]} />
                )}
                <button onClick={handleCloseVerify} className="eg-btn w-full py-2">
                  Close
                </button>
              </div>
            )}

            {/* Error */}
            {verifyState === "error" && (
              <div className="space-y-3">
                <div className="text-sm" style={{ color: "var(--danger)" }}>
                  {verifyError || "Verification failed"}
                </div>
                <div className="flex gap-3">
                  <button onClick={handleVerifyNow} className="eg-btn eg-btn-primary px-6 py-2">
                    Retry
                  </button>
                  <button onClick={handleCloseVerify} className="eg-btn px-4 py-2">
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
    </AppShell>
  );
}
