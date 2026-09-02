"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

const STATUS_STYLES: Record<string, string> = {
  started: "bg-blue-500/20 text-blue-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  completed_with_errors: "bg-amber-500/20 text-amber-400",
  failed: "bg-pink-500/20 text-pink-400",
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
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (filterType) params.set("import_type", filterType);
    if (filterStatus) params.set("status", filterStatus);

    try {
      const res = await fetch(`${API}/api/v1/import/audit?${params}`);
      if (res.ok) {
        const data: AuditListResponse = await res.json();
        setLogs(data.items);
        setTotal(data.total);
      }
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
      const res = await fetch(`${API}/api/v1/import/audit/${id}`);
      if (res.ok) {
        const data: AuditLogDetail = await res.json();
        setDetail(data);
      }
    } finally {
      setDetailLoading(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Import History
        </h1>
        <p className="text-[#999] mb-8">
          Audit log of all bulk import operations
        </p>

        <div className="flex gap-4 mb-6">
          <select
            value={filterType}
            onChange={(e) => {
              setFilterType(e.target.value);
              setPage(1);
            }}
            className="bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white text-sm focus:outline-none focus:border-cyan-500"
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
            className="bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white text-sm focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Statuses</option>
            <option value="started">Started</option>
            <option value="completed">Completed</option>
            <option value="completed_with_errors">Completed with Errors</option>
            <option value="failed">Failed</option>
          </select>

          <span className="text-[#666] text-sm self-center">
            {total} record{total !== 1 ? "s" : ""}
          </span>
        </div>

        {loading ? (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-16 text-[#666]">
            No audit records found
          </div>
        ) : (
          <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden mb-6">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                  <th className="px-6 py-3">Date/Time</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Operation</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Total</th>
                  <th className="px-6 py-3 text-right">OK</th>
                  <th className="px-6 py-3 text-right">Skipped</th>
                  <th className="px-6 py-3 text-right">Failed</th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className="border-b border-white/5 hover:bg-white/[0.02] cursor-pointer"
                    onClick={() => handleDetail(log.id)}
                  >
                    <td className="px-6 py-3 text-sm text-[#ccc]">
                      {formatDate(log.started_at)}
                    </td>
                    <td className="px-6 py-3 text-sm">
                      {TYPE_LABELS[log.import_type] || log.import_type}
                    </td>
                    <td className="px-6 py-3 text-sm capitalize">
                      {log.operation}
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className={`text-xs px-2 py-1 rounded-full ${STATUS_STYLES[log.status] || "bg-white/10 text-white"}`}
                      >
                        {log.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-sm text-right">
                      {log.total_rows}
                    </td>
                    <td className="px-6 py-3 text-sm text-right text-emerald-400">
                      {log.successful_rows}
                    </td>
                    <td className="px-6 py-3 text-sm text-right text-amber-400">
                      {log.skipped_rows}
                    </td>
                    <td className="px-6 py-3 text-sm text-right text-pink-400">
                      {log.failed_rows}
                    </td>
                    <td className="px-6 py-3 text-sm text-[#666]">
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
              className="px-3 py-1 rounded border border-white/10 text-sm disabled:opacity-30 hover:bg-white/5"
            >
              Prev
            </button>
            <span className="px-3 py-1 text-sm text-[#999]">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 rounded border border-white/10 text-sm disabled:opacity-30 hover:bg-white/5"
            >
              Next
            </button>
          </div>
        )}

        {detail && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <div className="bg-[#111] border border-white/10 rounded-lg p-6 max-w-lg w-full">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold">Audit Detail</h2>
                <button
                  onClick={() => setDetail(null)}
                  className="text-[#666] hover:text-white text-xl"
                >
                  &times;
                </button>
              </div>

              {detailLoading ? (
                <div className="text-center py-8">
                  <div className="inline-block w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[#999]">ID</span>
                    <span>{detail.id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#999]">Type</span>
                    <span>
                      {TYPE_LABELS[detail.import_type] || detail.import_type}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#999]">Operation</span>
                    <span className="capitalize">{detail.operation}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#999]">Status</span>
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${STATUS_STYLES[detail.status] || ""}`}
                    >
                      {detail.status.replace(/_/g, " ")}
                    </span>
                  </div>

                  <hr className="border-white/10" />

                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div>
                      <p className="text-lg font-bold">{detail.total_rows}</p>
                      <p className="text-[#666] text-xs">Total</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold text-emerald-400">
                        {detail.successful_rows}
                      </p>
                      <p className="text-[#666] text-xs">OK</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold text-amber-400">
                        {detail.skipped_rows}
                      </p>
                      <p className="text-[#666] text-xs">Skipped</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold text-pink-400">
                        {detail.failed_rows}
                      </p>
                      <p className="text-[#666] text-xs">Failed</p>
                    </div>
                  </div>

                  <hr className="border-white/10" />

                  <div className="flex justify-between">
                    <span className="text-[#999]">Started</span>
                    <span>{formatDate(detail.started_at)}</span>
                  </div>
                  {detail.completed_at && (
                    <div className="flex justify-between">
                      <span className="text-[#999]">Completed</span>
                      <span>{formatDate(detail.completed_at)}</span>
                    </div>
                  )}
                  {detail.actor && (
                    <div className="flex justify-between">
                      <span className="text-[#999]">Actor</span>
                      <span>{detail.actor}</span>
                    </div>
                  )}
                  {detail.error_summary && (
                    <div>
                      <p className="text-[#999] mb-1">Errors</p>
                      <p className="bg-pink-500/10 border border-pink-500/30 rounded p-3 text-pink-300 text-xs whitespace-pre-wrap">
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
          <Link
            href="/import"
            className="text-[#666] hover:text-white text-sm transition-colors"
          >
            &larr; Back to Import
          </Link>
        </div>
      </div>
    </div>
  );
}
