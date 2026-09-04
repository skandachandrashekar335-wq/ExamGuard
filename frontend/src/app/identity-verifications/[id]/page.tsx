"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getAttemptContext,
  startAttempt,
  verifyFace,
  evaluateEvidence,
  reviewAttempt,
  overrideDecision,
  cancelAttempt,
  ApiError,
} from "@/lib/iv-api";
import type {
  VerificationContext,
  IdentityVerificationEvidence,
} from "@/lib/types";
import CameraCapture from "@/components/CameraCapture";
import ImageUpload from "@/components/ImageUpload";
import EvidenceDisplay from "@/components/EvidenceDisplay";
import DecisionDisplay from "@/components/DecisionDisplay";
import VerificationState, {
  type VerificationUIState,
} from "@/components/VerificationState";
import AuditTimeline from "@/components/AuditTimeline";
import OverrideDialog from "@/components/OverrideDialog";

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

export default function IdentityVerificationDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const [ctx, setCtx] = useState<VerificationContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [uiState, setUiState] = useState<VerificationUIState>("READY");

  const [referenceImage, setReferenceImage] = useState<Blob | null>(null);
  const [probeImage, setProbeImage] = useState<Blob | null>(null);
  const [probeDataUrl, setProbeDataUrl] = useState<string | null>(null);

  const [verifyError, setVerifyError] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const [showReview, setShowReview] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");
  const [showOverride, setShowOverride] = useState(false);

  const fetchContext = useCallback(async () => {
    try {
      const data = await getAttemptContext(id);
      setCtx(data);
      setError("");
    } catch {
      setError("Attempt not found");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchContext();
  }, [fetchContext]);

  const attempt = ctx?.attempt;
  const evidence = ctx?.evidence || [];
  const isTerminal = attempt
    ? ["COMPLETED", "FAILED", "CANCELLED"].includes(attempt.status)
    : false;
  const canVerify = attempt
    ? ["CREATED", "IN_PROGRESS"].includes(attempt.status)
    : false;

  const handleVerify = async () => {
    if (!referenceImage || !probeImage) return;
    setVerifyError("");
    setActionMsg("");
    setUiState("SUBMITTING");
    try {
      const refBase64 = await fileToBase64(referenceImage);
      const probeBase64 = await fileToBase64(probeImage);

      setUiState("VERIFYING");
      await verifyFace(id, {
        reference_image: refBase64,
        probe_image: probeBase64,
        reference_image_format: referenceImage.type || "image/jpeg",
        probe_image_format: probeImage.type || "image/jpeg",
      });

      setUiState("EVALUATING");
      await evaluateEvidence(id);

      setUiState("COMPLETED");
      await fetchContext();
    } catch (e: unknown) {
      setUiState("READY");
      if (e instanceof ApiError) {
        setVerifyError(e.message);
      } else {
        setVerifyError("Verification failed");
      }
    }
  };

  const handleReview = async () => {
    setActionMsg("");
    try {
      await reviewAttempt(id, reviewNotes || undefined);
      setActionMsg("Review requested");
      setShowReview(false);
      setReviewNotes("");
      await fetchContext();
    } catch (e: unknown) {
      setActionMsg(e instanceof ApiError ? e.message : "Review failed");
    }
  };

  const handleOverride = async (newDecision: string, reason: string) => {
    await overrideDecision(id, { new_decision: newDecision, reason });
    setActionMsg("Override recorded");
    setShowOverride(false);
    await fetchContext();
  };

  const handleCancel = async () => {
    setActionMsg("");
    try {
      await cancelAttempt(id);
      setActionMsg("Attempt cancelled");
      await fetchContext();
    } catch (e: unknown) {
      setActionMsg(e instanceof ApiError ? e.message : "Cancel failed");
    }
  };

  const handleStart = async () => {
    setActionMsg("");
    try {
      await startAttempt(id);
      setActionMsg("Attempt started");
      await fetchContext();
    } catch (e: unknown) {
      setActionMsg(e instanceof ApiError ? e.message : "Start failed");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
        <div className="max-w-5xl mx-auto">
          <span className="eg-mono text-[var(--text-muted)]">
            Loading attempt...
          </span>
        </div>
      </div>
    );
  }

  if (error || !attempt) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
        <div className="max-w-5xl mx-auto">
          <p className="text-red-400 mb-4">{error || "Not found"}</p>
          <Link
            href="/identity-verifications"
            className="eg-mono-sm text-white hover:text-[var(--text-secondary)]"
          >
            Back to list
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <Link
          href="/identity-verifications"
          className="eg-mono-sm text-[var(--text-secondary)] hover:text-white mb-6 inline-block transition-colors"
        >
          Identity Verifications
        </Link>

        <div className="flex flex-wrap items-center gap-3 mb-6">
          <h1 className="eg-display text-2xl">
            Verification #{attempt.id}
          </h1>
          <span className="eg-mono-sm border border-white/20 px-2 py-0.5">
            {attempt.status}
          </span>
          <span className="eg-mono-sm border border-white/20 px-2 py-0.5">
            {attempt.decision}
          </span>
        </div>

        {actionMsg && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-3 mb-4">
            <span className="eg-mono-sm text-[var(--text-secondary)]">
              {actionMsg}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column — Camera + Images */}
          <div className="lg:col-span-2 space-y-6">
            {/* Verification State */}
            <VerificationState current={uiState} />

            {/* Camera + Reference Image */}
            {canVerify && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <ImageUpload
                  label="Reference Image"
                  onImage={(blob) => setReferenceImage(blob)}
                  onClear={() => setReferenceImage(null)}
                  disabled={uiState !== "READY"}
                />
                <CameraCapture
                  onCapture={(blob, url) => {
                    setProbeImage(blob);
                    setProbeDataUrl(url);
                  }}
                  onRetake={() => {
                    setProbeImage(null);
                    setProbeDataUrl(null);
                  }}
                  disabled={uiState !== "READY"}
                />
              </div>
            )}

            {/* Verify button */}
            {canVerify && (
              <div className="flex items-center gap-4">
                <button
                  onClick={handleVerify}
                  disabled={!referenceImage || !probeImage || uiState !== "READY"}
                  className="eg-btn-primary eg-btn px-6 py-2 disabled:opacity-30"
                >
                  Verify Identity
                </button>
                {verifyError && (
                  <span className="text-xs text-red-400">{verifyError}</span>
                )}
              </div>
            )}

            {/* Evidence */}
            <div className="border border-white/10 bg-[var(--bg-raised)] p-4">
              <h3 className="eg-mono-sm text-[var(--text-muted)] mb-3">
                Evidence
              </h3>
              <EvidenceDisplay evidence={evidence} />
            </div>

            {/* Decision */}
            <DecisionDisplay
              decision={attempt.decision}
              failureReason={attempt.failure_reason}
            />
          </div>

          {/* Right column — Context + Actions */}
          <div className="space-y-6">
            {/* Student context */}
            <div className="border border-white/10 bg-[var(--bg-raised)] p-4">
              <h3 className="eg-mono-sm text-[var(--text-muted)] mb-3">
                Candidate
              </h3>
              {ctx?.student ? (
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">USN</span>
                    <span className="font-mono">{ctx.student.usn}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Name</span>
                    <span>{ctx.student.name}</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[var(--text-muted)]">
                  No student linked
                </p>
              )}
            </div>

            {/* Exam context */}
            <div className="border border-white/10 bg-[var(--bg-raised)] p-4">
              <h3 className="eg-mono-sm text-[var(--text-muted)] mb-3">
                Exam
              </h3>
              {ctx?.exam ? (
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Exam</span>
                    <span>{ctx.exam.exam_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">
                      Subject ID
                    </span>
                    <span className="font-mono">{ctx.exam.subject_id}</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[var(--text-muted)]">
                  No exam linked
                </p>
              )}
            </div>

            {/* Attempt details */}
            <div className="border border-white/10 bg-[var(--bg-raised)] p-4">
              <h3 className="eg-mono-sm text-[var(--text-muted)] mb-3">
                Attempt
              </h3>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Method</span>
                  <span>{attempt.verification_method}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">
                    Registration
                  </span>
                  <span className="font-mono">
                    #{attempt.exam_registration_id}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">
                    Hall Ticket
                  </span>
                  <span className="font-mono">
                    {attempt.hall_ticket_id
                      ? `#${attempt.hall_ticket_id}`
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Created</span>
                  <span className="font-mono text-xs">
                    {new Date(attempt.created_at).toLocaleString()}
                  </span>
                </div>
                {attempt.started_at && (
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Started</span>
                    <span className="font-mono text-xs">
                      {new Date(attempt.started_at).toLocaleString()}
                    </span>
                  </div>
                )}
                {attempt.completed_at && (
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">
                      Completed
                    </span>
                    <span className="font-mono text-xs">
                      {new Date(attempt.completed_at).toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="border border-white/10 bg-[var(--bg-raised)] p-4">
              <h3 className="eg-mono-sm text-[var(--text-muted)] mb-3">
                Actions
              </h3>
              <div className="space-y-2">
                {attempt.status === "CREATED" && (
                  <button
                    onClick={handleStart}
                    className="eg-btn w-full py-2"
                  >
                    Start
                  </button>
                )}
                {isTerminal && (
                  <>
                    <button
                      onClick={() => setShowReview(!showReview)}
                      className="eg-btn w-full py-2"
                    >
                      Request Review
                    </button>
                    <button
                      onClick={() => setShowOverride(!showOverride)}
                      className="eg-btn w-full py-2"
                    >
                      Override Decision
                    </button>
                  </>
                )}
                {!isTerminal && attempt.status !== "CREATED" && (
                  <button
                    onClick={handleCancel}
                    className="eg-btn w-full py-2"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>

            {/* Review form */}
            {showReview && (
              <div className="border border-white/10 bg-[var(--bg-raised)] p-4">
                <h4 className="eg-mono-sm text-[var(--text-muted)] mb-3">
                  Review Notes
                </h4>
                <textarea
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  rows={3}
                  className="w-full bg-black border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30 resize-none mb-3"
                  placeholder="Optional notes..."
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setShowReview(false);
                      setReviewNotes("");
                    }}
                    className="eg-btn px-3 py-1"
                  >
                    Cancel
                  </button>
                  <button onClick={handleReview} className="eg-btn px-3 py-1">
                    Submit Review
                  </button>
                </div>
              </div>
            )}

            {/* Override form */}
            {showOverride && (
              <OverrideDialog
                currentDecision={attempt.decision}
                onConfirm={handleOverride}
                onCancel={() => setShowOverride(false)}
              />
            )}

            {/* Audit timeline */}
            <div className="border border-white/10 bg-[var(--bg-raised)] p-4">
              <h3 className="eg-mono-sm text-[var(--text-muted)] mb-3">
                Audit Trail
              </h3>
              <AuditTimeline attempt={attempt} evidence={evidence} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
