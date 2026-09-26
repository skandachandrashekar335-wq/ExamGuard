"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  getInvigilatorDashboard,
  startExam,
  endExam,
  type InvigilatorDashboard,
} from "@/lib/invigilator-api";
import { apiRequest } from "@/lib/api";
import { ApiError } from "@/lib/api";
import { getAttemptContext, verifyFace, evaluateEvidence, ApiError as IvApiError } from "@/lib/iv-api";
import type { VerificationContext } from "@/lib/types";
import CameraCapture, { type CameraCaptureHandle, type CameraState } from "@/components/CameraCapture";
import EvidenceDisplay from "@/components/EvidenceDisplay";
import DecisionDisplay from "@/components/DecisionDisplay";
import AppShell from "@/components/AppShell";

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1];
      if (base64) resolve(base64);
      else reject(new Error("Failed to encode image"));
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const onAbort = () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const t = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

function isRecoverableFaceMessage(msg: string): boolean {
  const m = msg.toLowerCase();
  return (
    m.includes("no usable face") ||
    m.includes("no face detected") ||
    m.includes("multiple faces")
  );
}

type VerifyPhase =
  | "idle"
  | "starting"
  | "ready"
  | "verifying"
  | "done"
  | "error";

type ErrorKind =
  | "reference_mismatch"
  | "not_enrolled"
  | "rate_limit"
  | "camera"
  | "server";

function classifyVerifyError(msg: string): ErrorKind {
  if (msg.includes("REFERENCE_MISMATCH")) return "reference_mismatch";
  if (msg.includes("CANDIDATE_NOT_ENROLLED")) return "not_enrolled";
  if (msg.toLowerCase().includes("rate limit")) return "rate_limit";
  const m = msg.toLowerCase();
  if (m.includes("camera")) return "camera";
  return "server";
}

function stripErrorPrefix(msg: string): string {
  const idx = msg.indexOf(":");
  if (idx > 0 && msg.slice(0, idx) === msg.slice(0, idx).toUpperCase()) {
    return msg.slice(idx + 1).trim();
  }
  return msg;
}

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

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  starting: { label: "Initializing", cls: "eg-badge eg-badge-info" },
  ready: { label: "Camera Ready", cls: "eg-badge eg-badge-success" },
  verifying: { label: "Verification in Progress", cls: "eg-badge eg-badge-warning" },
  verified: { label: "Verified", cls: "eg-badge eg-badge-success" },
  not_verified: { label: "Not Verified", cls: "eg-badge eg-badge-danger" },
  inconclusive: { label: "Inconclusive", cls: "eg-badge eg-badge-warning" },
  reference_mismatch: { label: "Reference Mismatch", cls: "eg-badge eg-badge-danger" },
  not_enrolled: { label: "Not Enrolled", cls: "eg-badge eg-badge-danger" },
  rate_limit: { label: "Rate Limited", cls: "eg-badge eg-badge-warning" },
  camera: { label: "Camera Error", cls: "eg-badge eg-badge-danger" },
  server: { label: "Verification Error", cls: "eg-badge eg-badge-danger" },
};

export default function InvigilatorPage() {
  const [data, setData] = useState<InvigilatorDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionMsgKind, setActionMsgKind] = useState<"success" | "danger">("success");

  const [students, setStudents] = useState<RegisteredStudent[]>([]);

  const [selectedStudent, setSelectedStudent] = useState<RegisteredStudent | null>(null);
  const [verifyAttemptId, setVerifyAttemptId] = useState<number | null>(null);
  const [verifyCtx, setVerifyCtx] = useState<VerificationContext | null>(null);
  const [verifyState, setVerifyState] = useState<VerifyPhase>("idle");
  const [verifyResult, setVerifyResult] = useState<{
    decision: string;
    evidence: unknown[];
    verifiedAt: string;
    provider: string | null;
    evidenceId: number | null;
  } | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [verifyErrorKind, setVerifyErrorKind] = useState<ErrorKind>("server");
  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [cameraMessage, setCameraMessage] = useState<string>("");
  const [loopStatus, setLoopStatus] = useState<string>("");
  const [cameraKey, setCameraKey] = useState(0);

  const cameraRef = useRef<CameraCaptureHandle>(null);
  const abortRef = useRef<AbortController | null>(null);
  const loopRunningRef = useRef(false);
  const verifyStateRef = useRef<VerifyPhase>("idle");
  const selectedRef = useRef<RegisteredStudent | null>(null);

  useEffect(() => {
    verifyStateRef.current = verifyState;
  }, [verifyState]);

  useEffect(() => {
    selectedRef.current = selectedStudent;
  }, [selectedStudent]);

  const stopVerificationLoop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    loopRunningRef.current = false;
  }, []);

  const handleCloseVerify = useCallback(() => {
    stopVerificationLoop();
    cameraRef.current?.stop();
    setVerifyAttemptId(null);
    setSelectedStudent(null);
    setVerifyCtx(null);
    setVerifyState("idle");
    setVerifyResult(null);
    setVerifyError(null);
    setCameraState("idle");
    setCameraMessage("");
    setLoopStatus("");
  }, [stopVerificationLoop]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const dash = await getInvigilatorDashboard();
      setData(dash);
      try {
        const studentsRes = await apiRequest<{ items: RegisteredStudent[]; total: number }>(
          `/api/v1/invigilator/registered-students`
        );
        const fresh = studentsRes.items || [];
        setStudents(fresh);
        // Stale-selection guard: if a data refresh (e.g. "Load Demo Data" on
        // the dashboard) removed the selected attempt or changed its
        // reference image, drop the open modal and all verification state
        // instead of showing a previous demo's candidate/reference.
        const active = selectedRef.current;
        if (active) {
          const updated = fresh.find(
            (s) => s.registration_id === active.registration_id
          );
          if (
            !updated ||
            updated.attempt_id !== active.attempt_id ||
            (updated.reference_face_url ?? null) !==
              (active.reference_face_url ?? null)
          ) {
            handleCloseVerify();
          }
        }
      } catch {
        setStudents([]);
      }
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to load dashboard";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [handleCloseVerify]);

  useEffect(() => { load(); }, [load]);

  const handleStart = async () => {
    try {
      setActionLoading(true);
      setActionMsg(null);
      const res = await startExam();
      setActionMsgKind("success");
      setActionMsg(`Exam started. Session ${res.session_id}`);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to start exam";
      setActionMsgKind("danger");
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
      setActionMsgKind("success");
      setActionMsg(`Exam ended. Session ${res.session_id}`);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to end exam";
      setActionMsgKind("danger");
      setActionMsg(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const runVerificationLoop = useCallback(
    async (attemptId: number) => {
      if (loopRunningRef.current) return;
      loopRunningRef.current = true;
      const ac = new AbortController();
      abortRef.current = ac;
      setVerifyState("verifying");
      setVerifyError(null);
      setLoopStatus("Position your face inside the frame");

      try {
        while (
          !ac.signal.aborted &&
          cameraRef.current?.getState() !== "active"
        ) {
          await sleep(250, ac.signal);
        }
        if (ac.signal.aborted) return;

        setLoopStatus("Look directly at the camera — keep your face visible");
        await sleep(1500, ac.signal);

        while (!ac.signal.aborted) {
          const blob = await cameraRef.current?.grabFrame();
          if (!blob) {
            setLoopStatus("Waiting for camera frame...");
            await sleep(800, ac.signal);
            continue;
          }

          setVerifyState("verifying");
          setLoopStatus("Verification in progress");

          try {
            const probeB64 = await blobToBase64(blob);
            await verifyFace(
              attemptId,
              {
                probe_image: probeB64,
                probe_image_format: "image/jpeg",
              },
              ac.signal,
            );
            await evaluateEvidence(attemptId, ac.signal);
            const updated = await getAttemptContext(attemptId);
            if (ac.signal.aborted) return;
            setVerifyCtx(updated);

            const evidence = updated.evidence || [];
            const similarity = evidence.find(
              (e) => e.signal_type === "similarity_score",
            );
            const providerEv = evidence.find((e) => e.provider_name);
            setVerifyResult({
              decision: updated.attempt.decision,
              evidence,
              verifiedAt: new Date().toISOString(),
              provider: providerEv?.provider_name || null,
              evidenceId: similarity?.id ?? null,
            });
            setVerifyState("done");
            setLoopStatus("Verification complete");
            await load();
            return;
          } catch (e: unknown) {
            if (isAbortError(e)) return;
            const msg = e instanceof IvApiError ? e.message : "Verification failed";

            if (isRecoverableFaceMessage(msg)) {
              setVerifyState("verifying");
              setLoopStatus(msg);
              await sleep(1600, ac.signal);
              continue;
            }

            const kind = classifyVerifyError(msg);
            if (kind === "rate_limit") {
              setVerifyErrorKind("rate_limit");
              setVerifyError(stripErrorPrefix(msg));
              setVerifyState("error");
              return;
            }
            if (kind === "reference_mismatch" || kind === "not_enrolled") {
              setVerifyErrorKind(kind);
              setVerifyError(stripErrorPrefix(msg));
              setVerifyState("error");
              return;
            }

            const lower = msg.toLowerCase();
            if (
              lower.includes("status '") &&
              (lower.includes("completed") ||
                lower.includes("failed") ||
                lower.includes("cancelled"))
            ) {
              try {
                const updated = await getAttemptContext(attemptId);
                setVerifyCtx(updated);
                if (
                  updated.attempt.decision &&
                  updated.attempt.decision !== "PENDING"
                ) {
                  setVerifyResult({
                    decision: updated.attempt.decision,
                    evidence: updated.evidence || [],
                    verifiedAt:
                      updated.attempt.completed_at || new Date().toISOString(),
                    provider:
                      (updated.evidence || []).find((e) => e.provider_name)
                        ?.provider_name || null,
                    evidenceId: null,
                  });
                  setVerifyState("done");
                  return;
                }
              } catch {
                /* fall through */
              }
            }

            setVerifyErrorKind("server");
            setVerifyError(stripErrorPrefix(msg));
            setVerifyState("error");
            return;
          }
        }
      } catch (e: unknown) {
        if (!isAbortError(e)) {
          setVerifyErrorKind("server");
          setVerifyError(e instanceof Error ? e.message : "Verification failed");
          setVerifyState("error");
        }
      } finally {
        loopRunningRef.current = false;
      }
    },
    [load],
  );

  const handleStartVerify = async (student: RegisteredStudent) => {
    const attemptId = student.attempt_id;
    if (!attemptId) return;
    stopVerificationLoop();
    setSelectedStudent(student);
    setVerifyAttemptId(attemptId);
    setVerifyState("starting");
    setVerifyResult(null);
    setVerifyError(null);
    setVerifyCtx(null);
    setCameraState("idle");
    setCameraMessage("");
    setLoopStatus("Starting camera...");
    setCameraKey((k) => k + 1);

    try {
      const ctx = await getAttemptContext(attemptId);
      setVerifyCtx(ctx);

      if (
        ctx.attempt.decision &&
        ctx.attempt.decision !== "PENDING" &&
        (ctx.attempt.status === "COMPLETED" || ctx.attempt.status === "FAILED")
      ) {
        setVerifyResult({
          decision: ctx.attempt.decision,
          evidence: ctx.evidence || [],
          verifiedAt: ctx.attempt.completed_at || new Date().toISOString(),
          provider:
            (ctx.evidence || []).find((e) => e.provider_name)?.provider_name ||
            null,
          evidenceId: null,
        });
        setVerifyState("done");
        setLoopStatus("Verification complete");
        return;
      }
    } catch {
      setVerifyErrorKind("server");
      setVerifyError("Failed to load attempt context");
      setVerifyState("error");
    }
  };

  const handleCameraState = useCallback(
    (state: CameraState, message?: string) => {
      setCameraState(state);
      if (message) setCameraMessage(message);
      const phase = verifyStateRef.current;
      if (state === "active" && phase === "starting") {
        setVerifyState("ready");
        setLoopStatus("Position your face inside the frame");
      }
      if (state === "requesting" && (phase === "starting" || phase === "ready")) {
        setLoopStatus("Starting camera...");
      }
      if ((state === "error" || state === "unsupported") && phase !== "done") {
        stopVerificationLoop();
        setLoopStatus(
          state === "unsupported" ? "Camera unavailable" : message || "Camera unavailable",
        );
        setVerifyErrorKind("camera");
        setVerifyError(
          state === "unsupported"
            ? "Camera is not available in this browser"
            : message || "Camera unavailable",
        );
        setVerifyState("error");
      }
    },
    [stopVerificationLoop],
  );

  const handleVerifyNow = () => {
    if (!verifyAttemptId) return;
    void runVerificationLoop(verifyAttemptId);
  };

  const handleRetry = () => {
    if (!verifyAttemptId) return;
    stopVerificationLoop();
    cameraRef.current?.stop();
    setVerifyError(null);
    setVerifyResult(null);
    setVerifyState("starting");
    setLoopStatus("Starting camera...");
    setCameraState("idle");
    setCameraKey((k) => k + 1);
  };

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      // CameraCapture stops its own tracks on unmount (its internal cleanup).
    };
  }, []);

  const statusKey = (() => {
    if (verifyState === "starting") return "starting";
    if (verifyState === "ready") return "ready";
    if (verifyState === "verifying") return "verifying";
    if (verifyState === "error") return verifyErrorKind;
    if (verifyState === "done" && verifyResult) {
      if (verifyResult.decision === "MATCH") return "verified";
      if (verifyResult.decision === "NO_MATCH") return "not_verified";
      return "inconclusive";
    }
    return "starting";
  })();
  const statusBadge = STATUS_BADGE[statusKey] || STATUS_BADGE.server;

  if (loading) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-empty">
            <p className="eg-empty-title">Loading invigilator dashboard...</p>
          </div>
        </div>
      </AppShell>
    );
  }
  if (error) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-alert eg-alert-danger">Error: {error}</div>
        </div>
      </AppShell>
    );
  }
  if (!data) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-empty">
            <p className="eg-empty-title">No data</p>
          </div>
        </div>
      </AppShell>
    );
  }

  const { profile: p } = data;

  const refUrl =
    verifyCtx?.attempt?.reference_face_url || selectedStudent?.reference_face_url;
  const safeRefUrl = refUrl && /^https?:\/\//i.test(refUrl) ? refUrl : null;

  const canRetryError =
    verifyErrorKind === "rate_limit" ||
    verifyErrorKind === "camera" ||
    verifyErrorKind === "server";

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <p className="eg-breadcrumb">HOME / INVIGILATOR</p>
          <h1 className="eg-page-title">Invigilator Control Center</h1>
          <p className="eg-page-desc">
            Supervise your assigned examination and verify candidate identity live.
          </p>
        </div>

        {actionMsg && (
          <div
            className={`eg-alert mb-6 ${actionMsgKind === "danger" ? "eg-alert-danger" : "eg-alert-success"}`}
          >
            {actionMsg}
          </div>
        )}

        <div className="eg-grid-2 mb-6">
          <div className="glass-surface" style={{ padding: "1.5rem", borderRadius: "var(--radius-lg)" }}>
            <div className="eg-metric-label">Invigilator</div>
            <div className="eg-page-title" style={{ fontSize: "1.125rem", marginBottom: "0.75rem" }}>
              {p.full_name || p.email}
            </div>
            <p className="eg-page-desc" style={{ fontSize: "0.8125rem" }}>{p.email}</p>
          </div>

          <div className="glass-surface" style={{ padding: "1.5rem", borderRadius: "var(--radius-lg)" }}>
            <div className="eg-metric-label">Assigned Examination</div>
            <div className="eg-page-title" style={{ fontSize: "1.125rem", marginBottom: "0.75rem" }}>
              {p.exam_name}
            </div>
            <div className="eg-grid-2" style={{ gap: "0.5rem 1rem", fontSize: "0.8125rem" }}>
              <span style={{ color: "var(--text-muted)" }}>
                Subject: <span style={{ color: "var(--text-secondary)" }}>{p.subject_code} — {p.subject_name}</span>
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                Date: <span style={{ color: "var(--text-secondary)" }}>{p.exam_date}</span>
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                Time: <span style={{ color: "var(--text-secondary)" }}>{p.exam_start_time} — {p.exam_end_time}</span>
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                Hall: <span style={{ color: "var(--text-secondary)" }}>{p.hall_name} ({p.hall_building} {p.hall_room})</span>
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                Entry: <span style={{ color: "var(--text-secondary)" }}>{p.entry_point_name || "Not assigned"}</span>
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                Session: <span style={{ color: "var(--text-secondary)" }}>{p.session_status || "No session"}</span>
              </span>
            </div>
          </div>
        </div>

        <div className="glass-surface mb-6" style={{ padding: "1.5rem", borderRadius: "var(--radius-lg)" }}>
          <div className="eg-metric-label" style={{ marginBottom: "1rem" }}>Session Controls</div>
          <div className="flex gap-3" style={{ flexWrap: "wrap" }}>
            <button
              onClick={handleStart}
              disabled={!data.can_start || actionLoading}
              className="eg-btn eg-btn-primary"
            >
              {actionLoading ? "Starting..." : "Start Exam"}
            </button>
            <button
              onClick={handleEnd}
              disabled={!data.can_end || actionLoading}
              className="eg-btn eg-btn-danger"
            >
              {actionLoading ? "Ending..." : "End Exam"}
            </button>
            <button onClick={load} disabled={actionLoading} className="eg-btn">
              Refresh
            </button>
          </div>
          {!data.can_start && !data.can_end && p.session_status !== "IN_PROGRESS" && (
            <p className="eg-page-desc" style={{ marginTop: "0.75rem", fontSize: "0.8125rem" }}>
              Exam is not within the permitted start window. Start is allowed 15 minutes before the scheduled time.
            </p>
          )}
        </div>

        <div className="eg-grid-3 mb-6">
          <div className="eg-metric">
            <div className="eg-metric-label">Verified</div>
            <div className="eg-metric-value">{data.granted_count}</div>
          </div>
          <div className="eg-metric">
            <div className="eg-metric-label">Denied</div>
            <div className="eg-metric-value">{data.denied_count}</div>
          </div>
          <div className="eg-metric">
            <div className="eg-metric-label">Review</div>
            <div className="eg-metric-value">{data.escalated_count}</div>
          </div>
          <div className="eg-metric">
            <div className="eg-metric-label">Attendance</div>
            <div className="eg-metric-value">{data.attendance_count}</div>
          </div>
          <div className="eg-metric">
            <div className="eg-metric-label">Security Events</div>
            <div className="eg-metric-value">{data.security_event_count}</div>
          </div>
          <div className="eg-metric">
            <div className="eg-metric-label">Total Verifications</div>
            <div className="eg-metric-value">{data.verification_count}</div>
          </div>
        </div>

        <div className="glass-surface mb-6" style={{ padding: "1.5rem", borderRadius: "var(--radius-lg)" }}>
          <div className="eg-metric-label" style={{ marginBottom: "1rem" }}>Registered Candidates</div>
          {students.length === 0 ? (
            <p className="eg-page-desc" style={{ fontSize: "0.875rem" }}>
              No registered students found.
            </p>
          ) : (
            <div className="space-y-2">
              {students.map((s) => (
                <div
                  key={s.registration_id}
                  className="flex items-center justify-between"
                  style={{
                    gap: "0.75rem",
                    padding: "0.75rem 1rem",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--bg-glass-light)",
                    border: "1px solid var(--border)",
                    flexWrap: "wrap",
                  }}
                >
                  <div className="flex items-center" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
                    <span className="eg-mono-sm" style={{ color: "var(--text-muted)" }}>{s.student_usn}</span>
                    <span style={{ fontWeight: 500, fontSize: "0.875rem", color: "var(--text-primary)" }}>
                      {s.student_name}
                    </span>
                    {s.attempt_status && (
                      <span
                        className={`eg-badge ${
                          s.attempt_decision === "MATCH"
                            ? "eg-badge-success"
                            : s.attempt_decision === "NO_MATCH"
                              ? "eg-badge-danger"
                              : "eg-badge-warning"
                        }`}
                      >
                        {s.attempt_status} / {s.attempt_decision || "PENDING"}
                      </span>
                    )}
                    {s.reference_face_url ? (
                      <span className="eg-badge eg-badge-info">Reference Enrolled</span>
                    ) : (
                      <span className="eg-badge eg-badge-neutral">REFERENCE NOT ENROLLED</span>
                    )}
                  </div>
                  {s.attempt_id && (
                    <button
                      onClick={() => handleStartVerify(s)}
                      className="eg-btn eg-btn-primary"
                      style={{ fontSize: "0.75rem", height: "32px", padding: "0 0.875rem" }}
                    >
                      Verify Face
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {data.recent_verifications.length > 0 && (
          <div className="glass-surface" style={{ padding: "1.5rem", borderRadius: "var(--radius-lg)" }}>
            <div className="eg-metric-label" style={{ marginBottom: "1rem" }}>Verification History</div>
            <div className="space-y-2">
              {data.recent_verifications.map((v: Record<string, unknown>) => (
                <div
                  key={v.id as number}
                  className="flex items-center"
                  style={{
                    gap: "0.75rem",
                    padding: "0.625rem 1rem",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--bg-glass-light)",
                    border: "1px solid var(--border)",
                    fontSize: "0.8125rem",
                    flexWrap: "wrap",
                  }}
                >
                  <span className="eg-mono-sm" style={{ color: "var(--text-faint)" }}>
                    #{v.id as number}
                  </span>
                  <span style={{ color: "var(--text-secondary)" }}>
                    Student {v.student_id as number}
                  </span>
                  <span
                    className={`eg-badge ${
                      v.status === "GRANTED"
                        ? "eg-badge-success"
                        : v.status === "DENIED"
                          ? "eg-badge-danger"
                          : "eg-badge-warning"
                    }`}
                  >
                    {v.status as string}
                  </span>
                  <span className="eg-mono-sm" style={{ color: "var(--text-faint)", marginLeft: "auto" }}>
                    {v.created_at as string}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {verifyAttemptId && (
          <div
            className="eg-modal-backdrop"
            onClick={() => {
              if (verifyState !== "verifying") handleCloseVerify();
            }}
          >
            <div
              className="eg-modal glass-surface glass"
              style={{ maxWidth: "640px" }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="eg-modal-header">
                <div>
                  <h2 className="eg-page-title" style={{ fontSize: "1.125rem", marginBottom: "0.25rem" }}>
                    Face Verification
                  </h2>
                  <p className="eg-page-desc" style={{ fontSize: "0.8125rem" }}>
                    {verifyCtx?.student
                      ? `${verifyCtx.student.name} (${verifyCtx.student.usn})`
                      : selectedStudent
                        ? `${selectedStudent.student_name} (${selectedStudent.student_usn})`
                        : `Attempt #${verifyAttemptId}`}
                  </p>
                </div>
                <div className="flex items-center" style={{ gap: "0.75rem" }}>
                  <span className={statusBadge.cls}>{statusBadge.label}</span>
                  <button
                    onClick={handleCloseVerify}
                    className="eg-modal-close"
                    aria-label="Close verification"
                  >
                    &times;
                  </button>
                </div>
              </div>

              <div className="eg-modal-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <div className="eg-grid-2">
                  <div>
                    <span className="eg-mono-sm" style={{ color: "var(--text-muted)", display: "block", marginBottom: "0.5rem" }}>
                      Stored Reference
                    </span>
                    {safeRefUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={safeRefUrl}
                        alt="Reference face"
                        style={{
                          width: "100%",
                          height: "128px",
                          objectFit: "cover",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border)",
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: "100%",
                          height: "128px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px dashed var(--border-strong)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        REFERENCE NOT ENROLLED
                      </div>
                    )}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem", fontSize: "0.8125rem" }}>
                    <div>
                      <span className="eg-mono-sm" style={{ color: "var(--text-muted)", display: "block" }}>
                        Candidate
                      </span>
                      <span style={{ color: "var(--text-primary)" }}>
                        {verifyCtx?.student?.name || selectedStudent?.student_name || "—"}
                      </span>
                    </div>
                    <div>
                      <span className="eg-mono-sm" style={{ color: "var(--text-muted)", display: "block" }}>
                        USN
                      </span>
                      <span className="eg-mono" style={{ color: "var(--text-primary)" }}>
                        {verifyCtx?.student?.usn || selectedStudent?.student_usn || "—"}
                      </span>
                    </div>
                    <div>
                      <span className="eg-mono-sm" style={{ color: "var(--text-muted)", display: "block" }}>
                        Camera
                      </span>
                      <span style={{ color: "var(--text-secondary)" }}>
                        {cameraState === "active"
                          ? "Camera ready"
                          : cameraState === "requesting"
                            ? "Starting camera..."
                            : cameraState === "error"
                              ? "Camera unavailable"
                              : "Initializing"}
                      </span>
                    </div>
                    <div>
                      <span className="eg-mono-sm" style={{ color: "var(--text-muted)", display: "block" }}>
                        Guidance
                      </span>
                      <span style={{ color: "var(--text-secondary)" }}>
                        {loopStatus || "Position your face inside the frame"}
                      </span>
                    </div>
                  </div>
                </div>

                {(verifyState === "starting" || verifyState === "ready" || verifyState === "verifying") && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    <CameraCapture
                      key={cameraKey}
                      ref={cameraRef}
                      onCapture={() => undefined}
                      onRetake={() => undefined}
                      autoStart
                      liveMode
                      onStateChange={handleCameraState}
                    />
                    {verifyState === "ready" && cameraState === "active" && (
                      <button
                        onClick={handleVerifyNow}
                        className="eg-btn eg-btn-primary"
                        style={{ width: "100%", height: "44px", fontSize: "0.875rem" }}
                      >
                        Verify Live Face
                      </button>
                    )}
                    {verifyState === "verifying" && (
                      <div
                        className="eg-alert eg-alert-success"
                        style={{ textAlign: "center", animation: "eg-pulse 1.5s ease-in-out infinite" }}
                      >
                        Verification in progress — hold still...
                      </div>
                    )}
                  </div>
                )}

                {verifyState === "done" && verifyResult && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <DecisionDisplay
                      decision={verifyResult.decision}
                      failureReason={verifyCtx?.attempt?.failure_reason || null}
                    />
                    <div style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "0.25rem", color: "var(--text-muted)" }}>
                      <span>
                        Candidate:{" "}
                        {verifyCtx?.student
                          ? `${verifyCtx.student.name} (${verifyCtx.student.usn})`
                          : selectedStudent
                            ? `${selectedStudent.student_name} (${selectedStudent.student_usn})`
                            : `Attempt #${verifyAttemptId}`}
                      </span>
                      <span>Verification time: {new Date(verifyResult.verifiedAt).toLocaleString()}</span>
                      <span>
                        Provider:{" "}
                        {verifyResult.provider
                          ? verifyResult.provider === "uniface"
                            ? "UniFace"
                            : verifyResult.provider
                          : "—"}
                      </span>
                      {verifyResult.evidenceId != null && (
                        <span>Evidence ID: #{verifyResult.evidenceId}</span>
                      )}
                    </div>
                    {verifyResult.evidence.length > 0 && (
                      <EvidenceDisplay evidence={verifyResult.evidence as VerificationContext["evidence"]} />
                    )}
                    <button onClick={handleCloseVerify} className="eg-btn" style={{ width: "100%" }}>
                      Close
                    </button>
                  </div>
                )}

                {verifyState === "error" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <div className="eg-alert eg-alert-danger">
                      <strong style={{ display: "block", marginBottom: "0.25rem" }}>
                        {verifyErrorKind === "reference_mismatch"
                          ? "Reference mismatch"
                          : verifyErrorKind === "not_enrolled"
                            ? "Candidate not enrolled"
                            : verifyErrorKind === "camera"
                              ? "Camera error"
                              : verifyErrorKind === "rate_limit"
                                ? "Rate limit reached"
                                : "Verification failed"}
                      </strong>
                      {verifyError || cameraMessage || "Verification failed"}
                      {verifyErrorKind === "reference_mismatch" && (
                        <span style={{ display: "block", marginTop: "0.375rem", fontSize: "0.75rem" }}>
                          The stored reference does not belong to this candidate. Contact the operator to correct the selection.
                        </span>
                      )}
                      {verifyErrorKind === "not_enrolled" && (
                        <span style={{ display: "block", marginTop: "0.375rem", fontSize: "0.75rem" }}>
                          This candidate is not registered for the current examination.
                        </span>
                      )}
                    </div>
                    <div className="flex gap-3">
                      {canRetryError && (
                        <button onClick={handleRetry} className="eg-btn eg-btn-primary" style={{ flex: 1 }}>
                          Retry
                        </button>
                      )}
                      <button
                        onClick={handleCloseVerify}
                        className="eg-btn"
                        style={{ flex: canRetryError ? 1 : undefined, width: canRetryError ? undefined : "100%" }}
                      >
                        Close
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
