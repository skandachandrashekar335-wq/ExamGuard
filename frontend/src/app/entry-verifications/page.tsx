"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  listEntryVerifications,
  createEntryVerification,
  type EntryVerification,
  type EntryVerificationCreate,
  ApiError,
} from "@/lib/entry-verification-api";
import AppShell from "@/components/AppShell";

const STATUS_BADGE: Record<string, string> = {
  PENDING: "eg-badge-info",
  IN_PROGRESS: "eg-badge-info",
  GRANTED: "eg-badge-success",
  DENIED: "eg-badge-danger",
  ESCALATED: "eg-badge-warning",
};

const CHECK_BADGE: Record<string, string> = {
  PENDING: "eg-badge-neutral",
  PASSED: "eg-badge-success",
  FAILED: "eg-badge-danger",
  SKIPPED: "eg-badge-neutral",
};

export default function EntryVerificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<EntryVerification[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState("");
  const [entryPointFilter, setEntryPointFilter] = useState("");
  const [studentFilter, setStudentFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<EntryVerificationCreate>({
    student_id: 0,
    exam_registration_id: 0,
    entry_point_id: 0,
    camera_id: null,
    hall_ticket_id: null,
  });
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listEntryVerifications({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
        entry_point_id: entryPointFilter || undefined,
        student_id: studentFilter || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load entry verifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, statusFilter, entryPointFilter, studentFilter]);

  const totalPages = Math.ceil(total / pageSize);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    setFormLoading(true);
    try {
      const created = await createEntryVerification({
        student_id: form.student_id,
        exam_registration_id: form.exam_registration_id,
        entry_point_id: form.entry_point_id,
        camera_id: form.camera_id || undefined,
        hall_ticket_id: form.hall_ticket_id || undefined,
      });
      router.push(`/entry-verifications/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("Failed to create entry verification");
      }
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <h1 className="eg-page-title">Entry Verifications</h1>
          <p className="eg-page-desc">
            Examination entry verification records — hall ticket, identity, and seat checks
          </p>
          <button
            onClick={() => setShowForm(!showForm)}
            className="eg-btn eg-btn-primary px-4 py-2 text-sm"
          >
            {showForm ? "Cancel" : "+ New Entry Verification"}
          </button>
        </div>

        {showForm && (
          <form
            onSubmit={handleCreate}
            className="glass-surface p-6 mb-8"
          >
            <h2 className="eg-mono text-sm text-[var(--text-secondary)] mb-4">
              Create Entry Verification
            </h2>
            {formError && (
              <div className="glass-surface p-3 mb-4" style={{ borderColor: "rgba(220,38,38,0.3)" }}>
                <span className="eg-mono text-sm" style={{ color: "var(--danger)" }}>{formError}</span>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="eg-label">
                  Student ID *
                </label>
                <input
                  type="number"
                  required
                  value={form.student_id || ""}
                  onChange={(e) =>
                    setForm({ ...form, student_id: Number(e.target.value) })
                  }
                  className="eg-input w-full"
                />
              </div>
              <div>
                <label className="eg-label">
                  Registration ID *
                </label>
                <input
                  type="number"
                  required
                  value={form.exam_registration_id || ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      exam_registration_id: Number(e.target.value),
                    })
                  }
                  className="eg-input w-full"
                />
              </div>
              <div>
                <label className="eg-label">
                  Entry Point ID *
                </label>
                <input
                  type="number"
                  required
                  value={form.entry_point_id || ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      entry_point_id: Number(e.target.value),
                    })
                  }
                  className="eg-input w-full"
                />
              </div>
              <div>
                <label className="eg-label">
                  Camera ID
                </label>
                <input
                  type="number"
                  value={form.camera_id ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      camera_id: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="eg-input w-full"
                  placeholder="Optional"
                />
              </div>
              <div>
                <label className="eg-label">
                  Hall Ticket ID
                </label>
                <input
                  type="number"
                  value={form.hall_ticket_id ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      hall_ticket_id: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                  className="eg-input w-full"
                  placeholder="Optional"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={formLoading}
              className="eg-btn eg-btn-primary px-4 py-2 text-sm disabled:opacity-30"
            >
              {formLoading ? "Creating..." : "Create Entry Verification"}
            </button>
          </form>
        )}

        <div className="eg-filter-bar mb-6">
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
            <option value="PENDING">Pending</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="GRANTED">Granted</option>
            <option value="DENIED">Denied</option>
            <option value="ESCALATED">Escalated</option>
          </select>
          <input
            type="text"
            placeholder="Entry point ID..."
            value={entryPointFilter}
            onChange={(e) => {
              setEntryPointFilter(e.target.value);
              setPage(1);
            }}
            className="eg-input w-40"
          />
        </div>

        {error && (
          <div className="glass-surface p-4 mb-6">
            <span className="eg-mono text-sm" style={{ color: "var(--danger)" }}>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="glass-surface p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">
              Loading entry verifications...
            </span>
          </div>
        ) : items.length === 0 ? (
          <div className="eg-empty">
            <div className="eg-empty-title">No entry verifications</div>
            <div className="eg-empty-desc">
              No entry verification records have been created yet.
            </div>
          </div>
        ) : (
          <div className="eg-table-wrap">
            <table className="eg-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Student</th>
                  <th>Reg</th>
                  <th>Entry Point</th>
                  <th>Hall</th>
                  <th>Status</th>
                  <th>Ticket</th>
                  <th>Identity</th>
                  <th>Seat</th>
                  <th>Created</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((ev) => (
                  <tr key={ev.id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>{ev.id}</td>
                    <td>#{ev.student_id}</td>
                    <td style={{ color: "var(--text-secondary)" }}>
                      #{ev.exam_registration_id}
                    </td>
                    <td style={{ color: "var(--text-secondary)" }}>
                      #{ev.entry_point_id}
                    </td>
                    <td style={{ color: "var(--text-secondary)" }}>
                      #{ev.exam_hall_id}
                    </td>
                    <td>
                      <span className={`eg-badge ${STATUS_BADGE[ev.status] || "eg-badge-neutral"}`}>
                        {ev.status}
                      </span>
                    </td>
                    <td>
                      <span className={`eg-badge ${CHECK_BADGE[ev.hall_ticket_check] || "eg-badge-neutral"}`}>
                        {ev.hall_ticket_check}
                      </span>
                    </td>
                    <td>
                      <span className={`eg-badge ${CHECK_BADGE[ev.identity_check] || "eg-badge-neutral"}`}>
                        {ev.identity_check}
                      </span>
                    </td>
                    <td>
                      <span className={`eg-badge ${CHECK_BADGE[ev.seat_check] || "eg-badge-neutral"}`}>
                        {ev.seat_check}
                      </span>
                    </td>
                    <td
                      style={{
                        color: "var(--text-muted)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.75rem",
                      }}
                    >
                      {new Date(ev.created_at).toLocaleDateString()}
                    </td>
                    <td className="text-right">
                      <Link
                        href={`/entry-verifications/${ev.id}`}
                        className="eg-mono-sm text-[var(--text-primary)] hover:text-[var(--text-secondary)] transition-colors"
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
          <div className="eg-pagination mt-4">
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
    </AppShell>
  );
}
