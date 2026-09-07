"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { listAttempts } from "@/lib/iv-api";
import type { IdentityVerificationAttempt } from "@/lib/types";

const STATUS_CLASSES: Record<string, string> = {
  CREATED: "eg-badge eg-badge-info",
  IN_PROGRESS: "eg-badge eg-badge-warning",
  COMPLETED: "eg-badge eg-badge-success",
  FAILED: "eg-badge eg-badge-danger",
  CANCELLED: "eg-badge eg-badge-neutral",
};

const DECISION_CLASSES: Record<string, string> = {
  PENDING: "eg-badge eg-badge-neutral",
  MATCH: "eg-badge eg-badge-success",
  NO_MATCH: "eg-badge eg-badge-danger",
  INCONCLUSIVE: "eg-badge eg-badge-warning",
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
    <AppShell>
      <div className="eg-page">
        <div className="eg-breadcrumb">
          <Link href="/identity-verifications">Identity Verifications</Link>
        </div>

        <div className="eg-page-header">
          <h1 className="eg-page-title">Identity Verifications</h1>
          <p className="eg-page-desc">
            Verification attempts — face, manual, or document-based
          </p>
        </div>

        <div className="eg-filter-bar">
          <input
            type="text"
            placeholder="Student ID..."
            value={studentFilter}
            onChange={(e) => {
              setStudentFilter(e.target.value);
              setPage(1);
            }}
            className="eg-input w-36"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="eg-select"
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
            className="eg-select"
          >
            <option value="">All decisions</option>
            <option value="PENDING">Pending</option>
            <option value="MATCH">Match</option>
            <option value="NO_MATCH">No Match</option>
            <option value="INCONCLUSIVE">Inconclusive</option>
          </select>
        </div>

        {error && (
          <div className="glass-surface p-4 mb-6">
            <span className="eg-badge eg-badge-danger">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="glass-surface p-12 text-center">
            <span className="eg-empty-desc">Loading attempts...</span>
          </div>
        ) : attempts.length === 0 ? (
          <div className="eg-empty">
            <h3 className="eg-empty-title">No verification attempts</h3>
            <p className="eg-empty-desc">
              No identity verification attempts have been created yet.
            </p>
          </div>
        ) : (
          <div className="eg-table-wrap glass-surface">
            <table className="eg-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Student</th>
                  <th>Registration</th>
                  <th>Method</th>
                  <th>Status</th>
                  <th>Decision</th>
                  <th>Created</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((a) => (
                  <tr key={a.id}>
                    <td className="font-mono text-sm">{a.id}</td>
                    <td className="text-sm">#{a.student_id}</td>
                    <td className="text-sm" style={{ color: "var(--text-secondary)" }}>
                      #{a.exam_registration_id}
                    </td>
                    <td className="text-sm" style={{ color: "var(--text-secondary)" }}>
                      {a.verification_method}
                    </td>
                    <td>
                      <span className={STATUS_CLASSES[a.status] || "eg-badge eg-badge-neutral"}>
                        {a.status}
                      </span>
                    </td>
                    <td>
                      <span className={DECISION_CLASSES[a.decision] || "eg-badge eg-badge-neutral"}>
                        {a.decision}
                      </span>
                    </td>
                    <td className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                      {new Date(a.created_at).toLocaleDateString()}
                    </td>
                    <td className="text-right">
                      <Link href={`/identity-verifications/${a.id}`} className="eg-btn">
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
              className="eg-btn disabled:opacity-30"
            >
              Prev
            </button>
            <span style={{ color: "var(--text-muted)" }}>
              {page} / {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn disabled:opacity-30"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
