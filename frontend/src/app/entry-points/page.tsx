"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import {
  listEntryPoints,
  createEntryPoint,
  updateEntryPoint,
  deactivateEntryPoint,
  listExamHalls,
  type EntryPoint,
  type EntryPointCreate,
  type ExamHall,
  ApiError,
} from "@/lib/camera-api";

export default function EntryPointsPage() {
  const [entryPoints, setEntryPoints] = useState<EntryPoint[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [editEP, setEditEP] = useState<EntryPoint | null>(null);
  const [form, setForm] = useState<EntryPointCreate>({
    name: "",
    code: "",
  });
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);

  const [halls, setHalls] = useState<ExamHall[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  async function loadHalls() {
    try {
      const data = await listExamHalls({ page_size: 100, include_inactive: true });
      setHalls(data.items);
    } catch {
      // Non-critical
    }
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listEntryPoints({
        page,
        page_size: pageSize,
        search: search || undefined,
        include_inactive: showInactive,
      });
      setEntryPoints(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load entry points");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, showInactive]);

  useEffect(() => {
    loadHalls();
  }, []);

  function hallLabel(id: number | null): string {
    if (!id) return "—";
    const h = halls.find((h) => h.id === id);
    return h ? `${h.building} ${h.room_number}` : `Hall #${id}`;
  }

  function openCreate() {
    setEditEP(null);
    setForm({ name: "", code: "" });
    setFormError("");
    setShowForm(true);
  }

  function openEdit(ep: EntryPoint) {
    setEditEP(ep);
    setForm({
      name: ep.name,
      code: ep.code,
      description: ep.description || "",
      location_detail: ep.location_detail || "",
      exam_hall_id: ep.exam_hall_id || undefined,
    });
    setFormError("");
    setShowForm(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError("");
    try {
      const payload: EntryPointCreate = {
        name: form.name,
        code: form.code,
      };
      if (form.description) payload.description = form.description;
      if (form.location_detail) payload.location_detail = form.location_detail;
      if (form.exam_hall_id) payload.exam_hall_id = form.exam_hall_id;

      if (editEP) {
        await updateEntryPoint(editEP.id, payload);
      } else {
        await createEntryPoint(payload);
      }
      setShowForm(false);
      load();
    } catch (e) {
      if (e instanceof ApiError) {
        setFormError(e.message);
      } else {
        setFormError("An unexpected error occurred");
      }
    } finally {
      setFormLoading(false);
    }
  }

  async function handleDeactivate(id: number) {
    try {
      await deactivateEntryPoint(id);
      setConfirmDelete(null);
      load();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to deactivate entry point"
      );
    }
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <p className="eg-breadcrumb">HOME / ENTRY POINTS</p>
          <h1 className="eg-page-title">Entry Points</h1>
          <p className="eg-page-desc">Manage examination entry gates and access points</p>
        </div>

        <div className="eg-filter-bar">
          <input
            type="text"
            placeholder="Search entry points..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            className="eg-input flex-1"
          />
          <label className="eg-label flex items-center gap-2">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => {
                setShowInactive(e.target.checked);
                setPage(1);
              }}
              className="eg-checkbox"
            />
            Include inactive
          </label>
          <button onClick={openCreate} className="eg-btn eg-btn-primary">
            + Add Entry Point
          </button>
        </div>

        {error && (
          <div className="eg-alert eg-alert-danger mb-6">
            {error}
          </div>
        )}

        {loading ? (
          <div className="eg-empty">
            <p className="eg-empty-title">Loading entry points...</p>
          </div>
        ) : entryPoints.length === 0 ? (
          <div className="eg-empty">
            <p className="eg-empty-title">No entry points configured</p>
            <p className="eg-empty-desc">Get started by adding your first entry point.</p>
            <button onClick={openCreate} className="eg-btn eg-btn-primary mt-4">
              + Add Entry Point
            </button>
          </div>
        ) : (
          <>
            <div className="eg-table-wrap">
              <table className="eg-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Code</th>
                    <th>Location</th>
                    <th>Hall</th>
                    <th>Active</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {entryPoints.map((ep) => (
                    <tr key={ep.id}>
                      <td>{ep.name}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>
                        {ep.code}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>
                        {ep.location_detail || ep.description || "—"}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>
                        {hallLabel(ep.exam_hall_id)}
                      </td>
                      <td>
                        <span
                          className={`eg-badge ${ep.is_active ? "eg-badge-success" : "eg-badge-danger"}`}
                        >
                          {ep.is_active ? "Yes" : "No"}
                        </span>
                      </td>
                      <td className="text-right">
                        <button onClick={() => openEdit(ep)} className="eg-btn text-xs mr-4">
                          Edit
                        </button>
                        {ep.is_active && (
                          <button
                            onClick={() => setConfirmDelete(ep.id)}
                            className="eg-btn eg-btn-danger text-xs"
                          >
                            Deactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="eg-pagination">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="eg-btn eg-btn-sm"
              >
                Previous
              </button>
              <span className="eg-pagination-info">
                {total} total · Page {page} of {totalPages || 1}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="eg-btn eg-btn-sm"
              >
                Next
              </button>
            </div>
          </>
        )}

        {showForm && (
          <div className="eg-modal-backdrop" onClick={() => setShowForm(false)}>
            <div className="eg-modal glass-surface glass" onClick={(e) => e.stopPropagation()}>
              <div className="eg-modal-header">
                <h2 className="eg-page-title text-lg">
                  {editEP ? "Edit Entry Point" : "Add Entry Point"}
                </h2>
                <button onClick={() => setShowForm(false)} className="eg-modal-close">&times;</button>
              </div>
              <form onSubmit={handleSubmit} className="eg-modal-body">
                {formError && (
                  <div className="eg-alert eg-alert-danger mb-4">
                    {formError}
                  </div>
                )}
                <div className="eg-field">
                  <label className="eg-label">Name *</label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    className="eg-input w-full"
                    placeholder="e.g. Main Gate"
                  />
                </div>
                <div className="eg-field">
                  <label className="eg-label">Code *</label>
                  <input
                    type="text"
                    required
                    value={form.code}
                    onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                    className="eg-input w-full"
                    style={{ fontFamily: "var(--font-mono)" }}
                    placeholder="e.g. MAIN_GATE"
                  />
                </div>
                <div className="eg-field">
                  <label className="eg-label">Description</label>
                  <input
                    type="text"
                    value={form.description || ""}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value || null }))}
                    className="eg-input w-full"
                    placeholder="Optional description"
                  />
                </div>
                <div className="eg-grid-2">
                  <div className="eg-field">
                    <label className="eg-label">Location Detail</label>
                    <input
                      type="text"
                      value={form.location_detail || ""}
                      onChange={(e) => setForm((f) => ({ ...f, location_detail: e.target.value || null }))}
                      className="eg-input w-full"
                      placeholder="e.g. Ground floor, east wing"
                    />
                  </div>
                  <div className="eg-field">
                    <label className="eg-label">Exam Hall</label>
                    <select
                      value={form.exam_hall_id || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          exam_hall_id: e.target.value ? Number(e.target.value) : null,
                        }))
                      }
                      className="eg-select w-full"
                    >
                      <option value="">None</option>
                      {halls.map((h) => (
                        <option key={h.id} value={h.id}>
                          {h.building} {h.room_number}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="flex gap-3 pt-2">
                  <button type="submit" disabled={formLoading} className="eg-btn eg-btn-primary">
                    {formLoading ? "Saving..." : editEP ? "Update Entry Point" : "Create Entry Point"}
                  </button>
                  <button type="button" onClick={() => setShowForm(false)} className="eg-btn">
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {confirmDelete !== null && (
          <div className="eg-modal-backdrop" onClick={() => setConfirmDelete(null)}>
            <div className="eg-modal glass-surface glass" onClick={(e) => e.stopPropagation()}>
              <h2 className="eg-page-title text-lg mb-4">Deactivate Entry Point</h2>
              <p className="eg-body mb-6">
                This will deactivate the entry point. It will no longer appear in active operations.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleDeactivate(confirmDelete)}
                  className="eg-btn eg-btn-danger"
                >
                  Deactivate
                </button>
                <button onClick={() => setConfirmDelete(null)} className="eg-btn">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
