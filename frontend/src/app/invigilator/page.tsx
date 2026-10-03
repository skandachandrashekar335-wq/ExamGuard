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
import {
  getManualReviewStatus,
  submitManualReview,
  type ManualReviewStatus,
} from "@/lib/attendance-api";
import {
  getAttemptContext,
  verifyFace,
  evaluateEvidence,
  reverifyAttempt,
  ApiError as IvApiError,
} from "@/lib/iv-api";
import type { VerificationContext } from "@/lib/types";
import CameraCapture, { type CameraCaptureHandle, type CameraState } from "@/components/CameraCapture";
import EvidenceDisplay from "@/components/EvidenceDisplay";
import DecisionDisplay from "@/components/DecisionDisplay";
import CheckSummaryDisplay from "@/components/CheckSummaryDisplay";
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

function formatAutomatedResult(ctx: VerificationContext | null): string {
  if (!ctx) return "Unavailable";
  const sim = ctx.evidence.find((e) => e.signal_type === "similarity_score");
  const live = ctx.evidence.find((e) => e.signal_type === "liveness");
  const parts: string[] = [ctx.attempt.decision || "PENDING"];
  const simValue = sim?.confidence ?? sim?.signal_value;
  if (simValue !== null && simValue !== undefined) {
    parts.push(`similarity ${Number(simValue).toFixed(3)}`);
  }
  if (ctx.match_threshold != null) {
    parts.push(`threshold ${ctx.match_threshold.toFixed(3)}`);
  }
  if (live?.signal_value) {
    parts.push(`liveness ${live.signal_value}`);
  }
  if (ctx.attempt.completed_at) {
    parts.push(new Date(ctx.attempt.completed_at).toLocaleString());
  }
  return parts.join(" · ");
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
  const verifyAttemptIdRef = useRef<number | null>(null);
  const autoVerifyRef = useRef(false);
  const reverifyLoadingRef = useRef(false);

  const [reviewStudent, setReviewStudent] = useState<RegisteredStudent | null>(null);
  const [reviewStatus, setReviewStatus] = useState<ManualReviewStatus | null>(null);
  const [reviewCtx, setReviewCtx] = useState<VerificationContext | null>(null);
  const [reviewOutcome, setReviewOutcome] = useState<{
    outcome: string;
    automated: string;
  } | null>(null);
  const [reverifyLoading, setReverifyLoading] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewAction, setReviewAction] = useState<"CHECK_IN" | "CHECK_OUT" | null>(null);
  const [reviewReason, setReviewReason] = useState("");
  const [reviewMsg, setReviewMsg] = useState<string | null>(null);
  const [reviewMsgKind, setReviewMsgKind] = useState<"success" | "danger">("success");
  const [probePreview, setProbePreview] = useState<{
    registrationId: number;
    url: string;
  } | null>(null);
  const probeUrlRef = useRef<string | null>(null);

  const [endConfirm, setEndConfirm] = useState(false);

  const setProbe = useCallback(
    (preview: { registrationId: number; url: string } | null) => {
      if (probeUrlRef.current) URL.revokeObjectURL(probeUrlRef.current);
      probeUrlRef.current = preview?.url ?? null;
      setProbePreview(preview);
    },
    [],
  );

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
    autoVerifyRef.current = false;
    setVerifyAttemptId(null);
    verifyAttemptIdRef.current = null;
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
    if (!data || actionLoading) return;
    if (data.profile.session_status === "IN_PROGRESS") {
      setActionMsgKind("success");
      setActionMsg("Exam session is already in progress.");
      return;
    }
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
    if (!data || actionLoading) return;
    const status = data.profile.session_status;
    if (status === "COMPLETED" || status === "CANCELLED") {
      setEndConfirm(false);
      setActionMsgKind("success");
      setActionMsg(`Exam session is already ${status}.`);
      return;
    }
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
      setEndConfirm(false);
    }
  };

  const handleOpenReview = async (student: RegisteredStudent) => {
    setReviewStudent(student);
    setReviewStatus(null);
    setReviewCtx(null);
    setReviewOutcome(null);
    setReviewMsg(null);
    setReviewReason("");
    setReviewLoading(true);
    try {
      const status = await getManualReviewStatus(student.registration_id);
      setReviewStatus(status);
      // Best-effort attempt context: exam/evidence/threshold shown in the
      // review panel. The decision itself stays server-authoritative.
      if (status.latest_attempt_id != null) {
        try {
          const ctx = await getAttemptContext(status.latest_attempt_id);
          setReviewCtx(ctx);
        } catch {
          setReviewCtx(null);
        }
      }
    } catch (e: unknown) {
      setReviewMsgKind("danger");
      setReviewMsg(
        e instanceof ApiError ? e.message : "Failed to load the review panel.",
      );
    } finally {
      setReviewLoading(false);
    }
  };

  const handleCloseReview = () => {
    if (reviewAction) return;
    setProbe(null);
    setReviewStudent(null);
    setReviewStatus(null);
    setReviewCtx(null);
    setReviewOutcome(null);
    setReviewMsg(null);
    setReviewReason("");
  };

  const handleSubmitReview = async (action: "CHECK_IN" | "CHECK_OUT") => {
    if (!reviewStudent || reviewAction) return;
    const reason = reviewReason.trim();
    if (!reason) {
      setReviewMsgKind("danger");
      setReviewMsg(
        "Enter a reason for this decision — it is recorded in the audit trail.",
      );
      return;
    }
    setReviewAction(action);
    setReviewMsg(null);
    try {
      await submitManualReview(reviewStudent.registration_id, {
        action,
        reason,
      });
      const fresh = await getManualReviewStatus(reviewStudent.registration_id);
      setReviewStatus(fresh);
      setReviewReason("");
      setReviewMsgKind("success");
      setReviewMsg("Manual review recorded.");
      setReviewOutcome({
        outcome:
          action === "CHECK_IN"
            ? "ALLOW ENTRY — candidate admitted (CHECKED_IN)"
            : "DENY ENTRY — candidate not admitted (CHECKED_OUT)",
        automated: formatAutomatedResult(reviewCtx),
      });
      await load();
    } catch (e: unknown) {
      setReviewMsgKind("danger");
      setReviewMsg(
        e instanceof ApiError
          ? e.message
          : "Failed to record the review decision.",
      );
    } finally {
      setReviewAction(null);
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
            const probeRegId = selectedRef.current?.registration_id;
            if (probeRegId != null) {
              setProbe({
                registrationId: probeRegId,
                url: URL.createObjectURL(blob),
              });
            }
            setVerifyState("done");
            setLoopStatus("Verification complete");
            await load();
            return;
          } catch (e: unknown) {
            if (isAbortError(e)) return;
            const msg = e instanceof IvApiError ? e.message : "The check did not complete. Please try again.";

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
          setVerifyError(e instanceof Error ? e.message : "The check did not complete. Please try again.");
          setVerifyState("error");
        }
      } finally {
        loopRunningRef.current = false;
      }
    },
    [load, setProbe],
  );

  const handleStartVerify = useCallback(
    async (
      student: RegisteredStudent,
      opts?: { autoVerify?: boolean },
    ) => {
      const attemptId = student.attempt_id;
      if (!attemptId) return;
      stopVerificationLoop();
      autoVerifyRef.current = opts?.autoVerify === true;
      setSelectedStudent(student);
      setVerifyAttemptId(attemptId);
      verifyAttemptIdRef.current = attemptId;
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
    },
    [stopVerificationLoop],
  );

  const handleCameraState = useCallback(
    (state: CameraState, message?: string) => {
      setCameraState(state);
      if (message) setCameraMessage(message);
      const phase = verifyStateRef.current;
      if (state === "active" && phase === "starting") {
        setVerifyState("ready");
        setLoopStatus("Position your face inside the frame");
        if (autoVerifyRef.current) {
          // REVERIFY: once the fresh camera session is live, go straight
          // into the verification loop ([REVERIFY] → [VERIFYING...]).
          autoVerifyRef.current = false;
          const aid = verifyAttemptIdRef.current;
          if (aid != null) {
            setTimeout(() => void runVerificationLoop(aid), 300);
          }
        }
      }
      if (state === "requesting" && (phase === "starting" || phase === "ready")) {
        setLoopStatus("Starting camera...");
      }
      if ((state === "error" || state === "unsupported") && phase !== "done") {
        stopVerificationLoop();
        autoVerifyRef.current = false;
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
    [stopVerificationLoop, runVerificationLoop],
  );

  const handleVerifyNow = () => {
    if (!verifyAttemptId) return;
    void runVerificationLoop(verifyAttemptId);
  };

  const handleRetry = () => {
    if (!verifyAttemptId) return;
    stopVerificationLoop();
    autoVerifyRef.current = false;
    cameraRef.current?.stop();
    setVerifyError(null);
    setVerifyResult(null);
    setVerifyState("starting");
    setLoopStatus("Starting camera...");
    setCameraState("idle");
    setCameraKey((k) => k + 1);
  };

  // REVERIFY — start a fresh attempt for the same candidate. The previous
  // attempt and all of its evidence stay untouched on the server; only the
  // new attempt receives camera frames, with a fresh rate-limit budget.
  const handleReverify = useCallback(
    async (source: RegisteredStudent, attemptId: number) => {
      if (reverifyLoadingRef.current) return;
      reverifyLoadingRef.current = true;
      setReverifyLoading(true);
      try {
        const fresh = await reverifyAttempt(attemptId);
        const updated: RegisteredStudent = {
          ...source,
          attempt_id: fresh.id,
          attempt_status: fresh.status,
          attempt_decision: fresh.decision,
          reference_face_url:
            fresh.reference_face_url ?? source.reference_face_url,
        };
        // Point the stale-selection guard at the fresh attempt BEFORE any
        // data refresh can observe the old one.
        selectedRef.current = updated;
        setStudents((prev) =>
          prev.map((s) =>
            s.registration_id === updated.registration_id ? updated : s,
          ),
        );
        await handleStartVerify(updated, { autoVerify: true });
      } catch (e: unknown) {
        autoVerifyRef.current = false;
        setVerifyErrorKind("server");
        setVerifyError(
          e instanceof ApiError
            ? e.message
            : "Failed to start a new verification attempt",
        );
        setVerifyState("error");
      } finally {
        reverifyLoadingRef.current = false;
        setReverifyLoading(false);
      }
    },
    [handleStartVerify],
  );

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (probeUrlRef.current) URL.revokeObjectURL(probeUrlRef.current);
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

  const reviewInconclusive =
    reviewStatus?.latest_attempt_decision === "INCONCLUSIVE";
  const reviewSessionActive = reviewStatus?.session_status === "IN_PROGRESS";
  const reviewCanAct =
    !!reviewStatus && reviewInconclusive && reviewSessionActive && !reviewAction;
  const reviewCheckInDisabled =
    !reviewCanAct || reviewStatus?.review_state !== "NOT_REVIEWED";
  const reviewCheckOutDisabled =
    !reviewCanAct || reviewStatus?.review_state === "CHECKED_OUT";

  const reviewSimEvidence = reviewCtx?.evidence.find(
    (e) => e.signal_type === "similarity_score",
  );
  const reviewLiveEvidence = reviewCtx?.evidence.find(
    (e) => e.signal_type === "liveness",
  );
  const reviewSimValue =
    reviewSimEvidence?.confidence ?? reviewSimEvidence?.signal_value;
  const reviewAttemptId = reviewStatus?.latest_attempt_id ?? null;

  const reviewRefUrl = reviewStudent?.reference_face_url;
  const reviewSafeRefUrl =
    reviewRefUrl && /^https?:\/\//i.test(reviewRefUrl) ? reviewRefUrl : null;
  const reviewProbeUrl =
    probePreview && reviewStudent
      ? probePreview.registrationId === reviewStudent.registration_id
        ? probePreview.url
        : null
      : null;

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
              {actionLoading && !endConfirm ? "Starting..." : "Start Exam"}
            </button>
            {endConfirm ? (
              <>
                <button
                  onClick={handleEnd}
                  disabled={actionLoading || !data.can_end}
                  className="eg-btn eg-btn-danger"
                >
                  {actionLoading ? "Ending..." : "Confirm End Exam"}
                </button>
                <button
                  onClick={() => setEndConfirm(false)}
                  disabled={actionLoading}
                  className="eg-btn"
                >
                  Keep Exam Running
                </button>
              </>
            ) : (
              <button
                onClick={() => setEndConfirm(true)}
                disabled={!data.can_end || actionLoading}
                className="eg-btn eg-btn-danger"
              >
                End Exam
              </button>
            )}
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
                  <div className="flex items-center" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
                    {s.attempt_id && (
                      <button
                        onClick={() => handleStartVerify(s)}
                        className="eg-btn eg-btn-primary"
                        style={{ fontSize: "0.75rem", height: "32px", padding: "0 0.875rem" }}
                      >
                        Verify Face
                      </button>
                    )}
                    {s.attempt_decision === "INCONCLUSIVE" && (
                      <button
                        onClick={() => void handleOpenReview(s)}
                        className="eg-btn"
                        style={{ fontSize: "0.75rem", height: "32px", padding: "0 0.875rem" }}
                      >
                        Review Identity
                      </button>
                    )}
                  </div>
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
                    <CheckSummaryDisplay
                      evidence={verifyResult.evidence as VerificationContext["evidence"]}
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
                      {verifyCtx?.match_threshold != null && (
                        <span>
                          Match threshold: {verifyCtx.match_threshold.toFixed(3)}
                        </span>
                      )}
                      {verifyResult.evidenceId != null && (
                        <span>Evidence ID: #{verifyResult.evidenceId}</span>
                      )}
                    </div>
                    {verifyResult.evidence.length > 0 && (
                      <EvidenceDisplay evidence={verifyResult.evidence as VerificationContext["evidence"]} />
                    )}
                    {verifyResult.decision === "NO_MATCH" && (
                      <div className="eg-alert eg-alert-danger" style={{ fontSize: "0.75rem" }}>
                        Automated result: identity not verified. A manual
                        allow is never available for a failed check — run
                        REVERIFY or contact an operator.
                      </div>
                    )}
                    {verifyResult.decision === "INCONCLUSIVE" && (
                      <div className="eg-alert" style={{ fontSize: "0.75rem" }}>
                        Automated result is inconclusive. An invigilator must
                        record ALLOW ENTRY or DENY ENTRY with a reason, or run
                        REVERIFY for a fresh check.
                      </div>
                    )}
                    {(verifyResult.decision === "NO_MATCH" ||
                      verifyResult.decision === "INCONCLUSIVE") &&
                      selectedStudent &&
                      verifyAttemptId != null && (
                        <button
                          onClick={() =>
                            void handleReverify(selectedStudent, verifyAttemptId)
                          }
                          disabled={reverifyLoading}
                          className="eg-btn eg-btn-primary"
                          style={{ width: "100%", whiteSpace: "normal" }}
                        >
                          {reverifyLoading
                            ? "Starting new check..."
                            : "REVERIFY"}
                        </button>
                      )}
                    {verifyResult.decision === "INCONCLUSIVE" && selectedStudent && (
                      <div className="flex gap-3">
                        <button
                          onClick={() => {
                            const student = selectedStudent;
                            handleCloseVerify();
                            void handleOpenReview(student);
                          }}
                          className="eg-btn eg-btn-primary"
                          style={{ flex: 1, whiteSpace: "normal" }}
                        >
                          ALLOW ENTRY
                        </button>
                        <button
                          onClick={() => {
                            const student = selectedStudent;
                            handleCloseVerify();
                            void handleOpenReview(student);
                          }}
                          className="eg-btn eg-btn-danger"
                          style={{ flex: 1, whiteSpace: "normal" }}
                        >
                          DENY ENTRY
                        </button>
                      </div>
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
                                  : "Check did not complete"}
                      </strong>
                      {verifyError || cameraMessage || "The check did not complete. Please try again."}
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

        {reviewStudent && (
          <div
            className="eg-modal-backdrop"
            onClick={() => {
              if (!reviewAction) handleCloseReview();
            }}
          >
            <div
              className="eg-modal glass-surface glass"
              style={{ maxWidth: "720px" }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="eg-modal-header">
                <div>
                  <h2 className="eg-page-title" style={{ fontSize: "1.125rem", marginBottom: "0.25rem" }}>
                    Identity Review
                  </h2>
                  <p className="eg-page-desc" style={{ fontSize: "0.8125rem" }}>
                    {reviewStudent.student_name} ({reviewStudent.student_usn})
                  </p>
                </div>
                <div className="flex items-center" style={{ gap: "0.75rem" }}>
                  <span
                    className={`eg-badge ${
                      reviewStatus?.review_state === "CHECKED_IN"
                        ? "eg-badge-success"
                        : reviewStatus?.review_state === "CHECKED_OUT"
                          ? "eg-badge-neutral"
                          : "eg-badge-warning"
                    }`}
                  >
                    {reviewStatus
                      ? reviewStatus.review_state.replace(/_/g, " ")
                      : "LOADING"}
                  </span>
                  <button
                    onClick={handleCloseReview}
                    disabled={!!reviewAction}
                    className="eg-modal-close"
                    aria-label="Close review"
                  >
                    &times;
                  </button>
                </div>
              </div>

              <div className="eg-modal-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {reviewMsg && (
                  <div
                    className={`eg-alert ${reviewMsgKind === "danger" ? "eg-alert-danger" : "eg-alert-success"}`}
                  >
                    {reviewMsg}
                  </div>
                )}
                {reviewOutcome && reviewMsgKind === "success" && (
                  <div
                    className="eg-alert eg-alert-success"
                    style={{ fontSize: "0.8125rem" }}
                  >
                    <strong style={{ display: "block", marginBottom: "0.25rem" }}>
                      Manual review recorded
                    </strong>
                    <span style={{ display: "block" }}>
                      Outcome: {reviewOutcome.outcome}
                    </span>
                    <span style={{ display: "block" }}>
                      Automated result: {reviewOutcome.automated}
                    </span>
                  </div>
                )}

                <div className="eg-grid-2">
                  <div>
                    <span className="eg-mono-sm" style={{ color: "var(--text-muted)", display: "block", marginBottom: "0.5rem" }}>
                      Stored Reference
                    </span>
                    {reviewSafeRefUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={reviewSafeRefUrl}
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
                  <div>
                    <span className="eg-mono-sm" style={{ color: "var(--text-muted)", display: "block", marginBottom: "0.5rem" }}>
                      Captured Check Image
                    </span>
                    {reviewProbeUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={reviewProbeUrl}
                        alt="Captured check image"
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
                        NO CAPTURED IMAGE
                      </div>
                    )}
                  </div>
                </div>

                {reviewLoading ? (
                  <p className="eg-page-desc" style={{ fontSize: "0.875rem" }}>
                    Loading review status...
                  </p>
                ) : reviewStatus ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <div className="eg-grid-2" style={{ gap: "0.5rem 1rem", fontSize: "0.8125rem" }}>
                      <span style={{ color: "var(--text-muted)" }}>
                        Automated result:{" "}
                        <span style={{ color: "var(--text-secondary)" }}>
                          {reviewStatus.latest_attempt_decision || "None"}
                        </span>
                      </span>
                      <span style={{ color: "var(--text-muted)" }}>
                        Exam session:{" "}
                        <span style={{ color: "var(--text-secondary)" }}>
                          {reviewStatus.session_status || "No session"}
                        </span>
                      </span>
                      {reviewCtx?.exam?.exam_name && (
                        <span style={{ color: "var(--text-muted)" }}>
                          Exam:{" "}
                          <span style={{ color: "var(--text-secondary)" }}>
                            {reviewCtx.exam.exam_name}
                          </span>
                        </span>
                      )}
                      {reviewStatus.seat_number && (
                        <span style={{ color: "var(--text-muted)" }}>
                          Seat:{" "}
                          <span style={{ color: "var(--text-secondary)" }}>
                            {reviewStatus.seat_number}
                          </span>
                        </span>
                      )}
                      {reviewSimValue != null && (
                        <span style={{ color: "var(--text-muted)" }}>
                          Similarity:{" "}
                          <span style={{ color: "var(--text-secondary)" }}>
                            {Number(reviewSimValue).toFixed(3)}
                          </span>
                        </span>
                      )}
                      {reviewCtx?.match_threshold != null && (
                        <span style={{ color: "var(--text-muted)" }}>
                          Match threshold:{" "}
                          <span style={{ color: "var(--text-secondary)" }}>
                            {reviewCtx.match_threshold.toFixed(3)}
                          </span>
                        </span>
                      )}
                      {reviewLiveEvidence?.signal_value && (
                        <span style={{ color: "var(--text-muted)" }}>
                          Liveness:{" "}
                          <span style={{ color: "var(--text-secondary)" }}>
                            {reviewLiveEvidence.signal_value}
                          </span>
                        </span>
                      )}
                      {reviewCtx?.attempt?.completed_at && (
                        <span style={{ color: "var(--text-muted)" }}>
                          Check time:{" "}
                          <span style={{ color: "var(--text-secondary)" }}>
                            {new Date(
                              reviewCtx.attempt.completed_at,
                            ).toLocaleString()}
                          </span>
                        </span>
                      )}
                      {reviewStatus.latest_attempt_id != null && (
                        <span style={{ color: "var(--text-muted)" }}>
                          Attempt:{" "}
                          <span style={{ color: "var(--text-secondary)" }}>
                            #{reviewStatus.latest_attempt_id}
                          </span>
                        </span>
                      )}
                    </div>

                    {!reviewInconclusive && (
                      <div className="eg-alert">
                        This candidate&apos;s latest identity check is{" "}
                        {reviewStatus.latest_attempt_decision || "missing"} —
                        manual review applies only to inconclusive checks.
                        {reviewStatus.review_state !== "NOT_REVIEWED" &&
                          " Review decisions already recorded are shown below."}
                      </div>
                    )}
                    {reviewInconclusive && !reviewSessionActive && (
                      <div className="eg-alert">
                        Exam session is{" "}
                        {reviewStatus.session_status || "not active"} — start
                        the exam before recording a review decision.
                      </div>
                    )}

                    <div>
                      <span className="eg-mono-sm" style={{ color: "var(--text-muted)", display: "block", marginBottom: "0.5rem" }}>
                        REVIEW HISTORY
                      </span>
                      {reviewStatus.events.length === 0 ? (
                        <p className="eg-page-desc" style={{ fontSize: "0.8125rem" }}>
                          No attendance events recorded yet.
                        </p>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                          {reviewStatus.events.map((ev) => (
                            <div
                              key={ev.id}
                              style={{
                                padding: "0.5rem 0.75rem",
                                borderRadius: "var(--radius-sm)",
                                background: "var(--bg-glass-light)",
                                border: "1px solid var(--border)",
                                fontSize: "0.75rem",
                                display: "flex",
                                flexDirection: "column",
                                gap: "0.25rem",
                              }}
                            >
                              <div className="flex items-center" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
                                <span
                                  className={`eg-badge ${
                                    ev.event_type === "MANUAL_CHECK_IN"
                                      ? "eg-badge-success"
                                      : ev.event_type === "MANUAL_CHECK_OUT"
                                        ? "eg-badge-warning"
                                        : "eg-badge-neutral"
                                  }`}
                                >
                                  {ev.event_type.replace(/_/g, " ")}
                                </span>
                                <span className="eg-mono-sm" style={{ color: "var(--text-muted)" }}>
                                  {ev.status_snapshot}
                                </span>
                                <span className="eg-mono-sm" style={{ color: "var(--text-faint)", marginLeft: "auto" }}>
                                  {new Date(ev.created_at).toLocaleString()}
                                </span>
                              </div>
                              {ev.reason && (
                                <span style={{ color: "var(--text-secondary)" }}>{ev.reason}</span>
                              )}
                              {ev.recorded_by && (
                                <span style={{ color: "var(--text-muted)" }}>
                                  Recorded by {ev.recorded_by}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div>
                      <p className="eg-page-desc" style={{ fontSize: "0.8125rem", marginBottom: "0.5rem" }}>
                        {reviewStatus.review_state === "CHECKED_IN"
                          ? "Candidate is ALLOWED ENTRY (checked in). A later DENY ENTRY records the candidate as absent."
                          : reviewStatus.review_state === "CHECKED_OUT"
                            ? "Candidate has been DENIED ENTRY. Attendance can only be changed afterwards by an admin correction."
                            : "ALLOW ENTRY admits the candidate. DENY ENTRY records that the candidate was not admitted. A reason is required for both."}
                      </p>
                      <label className="eg-label" htmlFor="manual-review-reason">
                        Reason (required)
                      </label>
                      <textarea
                        id="manual-review-reason"
                        value={reviewReason}
                        onChange={(e) => setReviewReason(e.target.value)}
                        rows={2}
                        maxLength={1000}
                        placeholder="What did you verify? e.g. Photo and ID card match, face check inconclusive"
                        className="eg-input w-full resize-none"
                        style={{ margin: "0.375rem 0 0.75rem" }}
                      />
                      <div className="flex gap-3">
                        <button
                          onClick={() => void handleSubmitReview("CHECK_IN")}
                          disabled={reviewCheckInDisabled}
                          className="eg-btn eg-btn-primary"
                          style={{ flex: 1, whiteSpace: "normal" }}
                        >
                          {reviewAction === "CHECK_IN"
                            ? "Allowing..."
                            : "ALLOW ENTRY"}
                        </button>
                        <button
                          onClick={() => void handleSubmitReview("CHECK_OUT")}
                          disabled={reviewCheckOutDisabled}
                          className="eg-btn eg-btn-danger"
                          style={{ flex: 1, whiteSpace: "normal" }}
                        >
                          {reviewAction === "CHECK_OUT"
                            ? "Denying..."
                            : "DENY ENTRY"}
                        </button>
                      </div>
                      <button
                        onClick={() => {
                          if (
                            !reviewStudent ||
                            reviewAttemptId == null ||
                            reviewAction ||
                            !reviewStatus.latest_attempt_decision ||
                            reviewStatus.latest_attempt_decision === "PENDING"
                          ) {
                            return;
                          }
                          const student = reviewStudent;
                          setReviewStudent(null);
                          void handleReverify(student, reviewAttemptId);
                        }}
                        disabled={
                          reviewAttemptId == null ||
                          !!reviewAction ||
                          reverifyLoading ||
                          !reviewStatus.latest_attempt_decision ||
                          reviewStatus.latest_attempt_decision === "PENDING"
                        }
                        className="eg-btn"
                        style={{
                          width: "100%",
                          whiteSpace: "normal",
                          marginTop: "0.75rem",
                        }}
                      >
                        {reverifyLoading
                          ? "Starting new check..."
                          : "REVERIFY"}
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
