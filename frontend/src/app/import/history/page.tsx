"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiRequest, qs } from "@/lib/api";

interface AuditLog {
  id: number;
  import_type: string;
  operation: string;
  status: string;
  total_rows: number;
  successful_rows: number;
  skipped_rows: number;
  failed_rows: number;
  started_at: string;
  completed_at: string | null;
}

interface AuditLogDetail extends AuditLog {
  error_summary: string | null;
  actor: string | null;
}

interface AuditListResponse {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
}

const TYPE_LABELS: Record<string, string> = {
  students: "Students",
  subjects_exams: "Subjects & Exams",
  registrations: "Registrations",
  registration_cancellations: "Reg. Cancellations",
  seat_assignments: "Seat Assignments",
  seat_assignment_cancellations: "Seat Assign. Cancellations",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export default function ImportHistoryPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<AuditLogDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiRequest<AuditListResponse>(
        `/api/v1/import/audit${qs({
          page: String(page),
          page_size: String(pageSize),
          ...(filterType ? { import_type: filterType } : {}),
          ...(filterStatus ? { status: filterStatus } : {}),
        })}`
      );
      setLogs(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filterType, filterStatus]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleDetail = async (id: number) => {
    setDetailLoading(true);
    try {
      const data = await apiRequest<AuditLogDetail>(
        `/api/v1/import/audit/${id}`
      );
      setDetail(data);
    } finally {
      setDetailLoading(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <div className="eg-breadcrumb">
            <Link href="/import">Import</Link> / History
          </div>
          <h1 className="eg-page-title">Import History</h1>
          <p className="eg-page-desc">Audit log of all bulk import operations</p>
        </div>

        <div className="eg-filter-bar mb-6">
          <select
            value={filterType}
            onChange={(e) => {
              setFilterType(e.target.value);
              setPage(1);
            }}
            className="eg-select"
          >
            <option value="">All Types</option>
            {Object.entries(TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => {
              setFilterStatus(e.target.value);
              setPage(1);
            }}
            className="eg-select"
          >
            <option value="">All Statuses</option>
            <option value="started">Started</option>
            <option value="completed">Completed</option>
            <option value="completed_with_errors">Completed with Errors</option>
            <option value="failed">Failed</option>
          </select>

          <span className="text-sm self-center" style={{ color: "var(--text-muted)" }}>
            {total} record{total !== 1 ? "s" : ""}
          </span>
        </div>

        {loading ? (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: "var(--accent)", borderTopColor: "transparent" }} />
          </div>
        ) : logs.length === 0 ? (
          <div className="eg-empty">
            <p className="eg-empty-title">No audit records found</p>
          </div>
        ) : (
          <div className="eg-table-wrap mb-6">
            <table className="eg-table">
              <thead>
                <tr>
                  <th>Date/Time</th>
                  <th>Type</th>
                  <th>Operation</th>
                  <th>Status</th>
                  <th className="text-right">Total</th>
                  <th className="text-right">OK</th>
                  <th className="text-right">Skipped</th>
                  <th className="text-right">Failed</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className="cursor-pointer"
                    onClick={() => handleDetail(log.id)}
                  >
                    <td className="text-sm" style={{ color: "var(--text-secondary)" }}>
                      {formatDate(log.started_at)}
                    </td>
                    <td className="text-sm">
                      {TYPE_LABELS[log.import_type] || log.import_type}
                    </td>
                    <td className="text-sm capitalize">
                      {log.operation}
                    </td>
                    <td>
                      <span
                        className={`eg-badge ${
                          log.status === "completed"
                            ? "eg-badge-success"
                            : log.status === "completed_with_errors"
                            ? "eg-badge-warning"
                            : log.status === "failed"
                            ? "eg-badge-danger"
                            : "eg-badge-info"
                        }`}
                      >
                        {log.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="text-sm text-right">
                      {log.total_rows}
                    </td>
                    <td className="text-sm text-right" style={{ color: "var(--success)" }}>
                      {log.successful_rows}
                    </td>
                    <td className="text-sm text-right" style={{ color: "var(--warning)" }}>
                      {log.skipped_rows}
                    </td>
                    <td className="text-sm text-right" style={{ color: "var(--danger)" }}>
                      {log.failed_rows}
                    </td>
                    <td className="text-sm" style={{ color: "var(--text-muted)" }}>
                      &rarr;
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="eg-btn disabled:opacity-30"
            >
              Prev
            </button>
            <span className="px-3 py-1 text-sm" style={{ color: "var(--text-secondary)" }}>
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="eg-btn disabled:opacity-30"
            >
              Next
            </button>
          </div>
        )}

        {detail && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <div className="glass-surface glass-medium p-6 max-w-lg w-full rounded-lg">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Audit Detail</h2>
                <button
                  onClick={() => setDetail(null)}
                  className="text-xl"
                  style={{ color: "var(--text-muted)" }}
                >
                  &times;
                </button>
              </div>

              {detailLoading ? (
                <div className="text-center py-8">
                  <div className="inline-block w-6 h-6 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: "var(--accent)", borderTopColor: "transparent" }} />
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span style={{ color: "var(--text-secondary)" }}>ID</span>
                    <span>{detail.id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: "var(--text-secondary)" }}>Type</span>
                    <span>
                      {TYPE_LABELS[detail.import_type] || detail.import_type}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: "var(--text-secondary)" }}>Operation</span>
                    <span className="capitalize">{detail.operation}</span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: "var(--text-secondary)" }}>Status</span>
                    <span
                      className={`eg-badge ${
                        detail.status === "completed"
                          ? "eg-badge-success"
                          : detail.status === "completed_with_errors"
                          ? "eg-badge-warning"
                          : detail.status === "failed"
                          ? "eg-badge-danger"
                          : "eg-badge-info"
                      }`}
                    >
                      {detail.status.replace(/_/g, " ")}
                    </span>
                  </div>

                  <hr style={{ borderColor: "var(--border)" }} />

                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div>
                      <p className="text-lg font-bold">{detail.total_rows}</p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>Total</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold" style={{ color: "var(--success)" }}>
                        {detail.successful_rows}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>OK</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold" style={{ color: "var(--warning)" }}>
                        {detail.skipped_rows}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>Skipped</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold" style={{ color: "var(--danger)" }}>
                        {detail.failed_rows}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>Failed</p>
                    </div>
                  </div>

                  <hr style={{ borderColor: "var(--border)" }} />

                  <div className="flex justify-between">
                    <span style={{ color: "var(--text-secondary)" }}>Started</span>
                    <span>{formatDate(detail.started_at)}</span>
                  </div>
                  {detail.completed_at && (
                    <div className="flex justify-between">
                      <span style={{ color: "var(--text-secondary)" }}>Completed</span>
                      <span>{formatDate(detail.completed_at)}</span>
                    </div>
                  )}
                  {detail.actor && (
                    <div className="flex justify-between">
                      <span style={{ color: "var(--text-secondary)" }}>Actor</span>
                      <span>{detail.actor}</span>
                    </div>
                  )}
                  {detail.error_summary && (
                    <div>
                      <p className="mb-1" style={{ color: "var(--text-secondary)" }}>Errors</p>
                      <p className="bg-[var(--danger-bg)] border border-[var(--danger-border)] rounded p-3 text-xs whitespace-pre-wrap" style={{ color: "var(--danger)" }}>
                        {detail.error_summary}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mt-8">
          <Link href="/import" className="eg-btn text-sm">
            &larr; Back to Import
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
