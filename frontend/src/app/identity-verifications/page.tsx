"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listAttempts } from "@/lib/iv-api";
import type { IdentityVerificationAttempt } from "@/lib/types";

const STATUS_CLASSES: Record<string, string> = {
  CREATED: "border-white/20 text-[var(--text-secondary)]",
  IN_PROGRESS: "border-white/30 text-white",
  COMPLETED: "border-white/40 text-white",
  FAILED: "border-white/20 text-[var(--text-secondary)]",
  CANCELLED: "border-white/10 text-[var(--text-muted)]",
};

const DECISION_CLASSES: Record<string, string> = {
  PENDING: "border-white/10 text-[var(--text-muted)]",
  MATCH: "border-white/40 text-white",
  NO_MATCH: "border-white/20 text-[var(--text-secondary)]",
  INCONCLUSIVE: "border-white/20 text-[var(--text-secondary)]",
};

export default function IdentityVerificationsPage() {
  const [attempts, setAttempts] = useState<IdentityVerificationAttempt[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState("");
  const [decisionFilter, setDecisionFilter] = useState("");
  const [studentFilter, setStudentFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listAttempts({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
        decision: decisionFilter || undefined,
        student_id: studentFilter || undefined,
      });
      setAttempts(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load verification attempts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, statusFilter, decisionFilter, studentFilter]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="eg-display text-3xl mb-2">
          Identity Verifications
        </h1>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Verification attempts — face, manual, or document-based
        </p>

        <div className="flex flex-wrap gap-3 mb-6">
          <input
            type="text"
            placeholder="Student ID..."
            value={studentFilter}
            onChange={(e) => {
              setStudentFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30 w-36"
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
            <option value="CREATED">Created</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
          <select
            value={decisionFilter}
            onChange={(e) => {
              setDecisionFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:border-white/30"
          >
            <option value="">All decisions</option>
            <option value="PENDING">Pending</option>
            <option value="MATCH">Match</option>
            <option value="NO_MATCH">No Match</option>
            <option value="INCONCLUSIVE">Inconclusive</option>
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
              Loading attempts...
            </span>
          </div>
        ) : attempts.length === 0 ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <h3 className="eg-mono text-[var(--text-secondary)] mb-2">
              No verification attempts
            </h3>
            <p className="text-sm text-[var(--text-muted)]">
              No identity verification attempts have been created yet.
            </p>
          </div>
        ) : (
          <div className="border border-white/10 bg-[var(--bg-raised)] overflow-hidden">
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
                    Registration
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Method
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Decision
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Created
                  </th>
                  <th className="px-4 py-3 text-right eg-mono-sm text-[var(--text-muted)]">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((a) => (
                  <tr
                    key={a.id}
                    className="border-b border-white/5 hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-sm">{a.id}</td>
                    <td className="px-4 py-3 text-sm">#{a.student_id}</td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                      #{a.exam_registration_id}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                      {a.verification_method}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-[10px] eg-mono border px-2 py-0.5 ${
                          STATUS_CLASSES[a.status] || "border-white/10 text-[var(--text-muted)]"
                        }`}
                      >
                        {a.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-[10px] eg-mono border px-2 py-0.5 ${
                          DECISION_CLASSES[a.decision] || "border-white/10 text-[var(--text-muted)]"
                        }`}
                      >
                        {a.decision}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono">
                      {new Date(a.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/identity-verifications/${a.id}`}
                        className="eg-mono-sm text-white hover:text-[var(--text-secondary)] transition-colors"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
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
