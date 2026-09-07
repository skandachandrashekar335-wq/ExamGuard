"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import {
  listCameras,
  createCamera,
  updateCamera,
  deactivateCamera,
  listExamHalls,
  type Camera,
  type CameraCreate,
  type ExamHall,
  ApiError,
} from "@/lib/camera-api";

const STATUS_OPTIONS = ["ONLINE", "OFFLINE", "UNKNOWN", "DISABLED"] as const;

function formatTimestamp(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString();
}

function healthReasonLabel(reason: string | null): string {
  if (!reason) return "—";
  const labels: Record<string, string> = {
    DEVICE_RESPONDED: "Device Responded",
    DEVICE_UNREACHABLE: "Device Unreachable",
    DEVICE_DISABLED: "Device Disabled",
    NO_OBSERVATION: "No Observation",
  };
  return labels[reason] || reason;
}

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [editCamera, setEditCamera] = useState<Camera | null>(null);
  const [form, setForm] = useState<CameraCreate>({
    name: "",
    device_identifier: "",
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
      // Non-critical — selectors will be empty
    }
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listCameras({
        page,
        page_size: pageSize,
        search: search || undefined,
        status: statusFilter || undefined,
        include_inactive: showInactive,
      });
      setCameras(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cameras");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, showInactive, statusFilter]);

  useEffect(() => {
    loadHalls();
  }, []);

  function hallLabel(id: number | null): string {
    if (!id) return "—";
    const h = halls.find((h) => h.id === id);
    return h ? `${h.building} ${h.room_number}` : `Hall #${id}`;
  }

  function openCreate() {
    setEditCamera(null);
    setForm({ name: "", device_identifier: "" });
    setFormError("");
    setShowForm(true);
  }

  function openEdit(c: Camera) {
    setEditCamera(c);
    setForm({
      name: c.name,
      device_identifier: c.device_identifier,
      camera_type: c.camera_type || "",
      manufacturer: c.manufacturer || "",
      model_name: c.model_name || "",
      resolution_width: c.resolution_width || undefined,
      resolution_height: c.resolution_height || undefined,
      exam_hall_id: c.exam_hall_id || undefined,
      connection_info: c.connection_info || "",
    });
    setFormError("");
    setShowForm(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError("");
    try {
      const payload: CameraCreate = {
        name: form.name,
        device_identifier: form.device_identifier,
      };
      if (form.camera_type) payload.camera_type = form.camera_type;
      if (form.manufacturer) payload.manufacturer = form.manufacturer;
      if (form.model_name) payload.model_name = form.model_name;
      if (form.resolution_width) payload.resolution_width = form.resolution_width;
      if (form.resolution_height) payload.resolution_height = form.resolution_height;
      if (form.exam_hall_id) payload.exam_hall_id = form.exam_hall_id;
      if (form.connection_info) payload.connection_info = form.connection_info;

      if (editCamera) {
        await updateCamera(editCamera.id, payload);
      } else {
        await createCamera(payload);
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
      await deactivateCamera(id);
      setConfirmDelete(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to deactivate camera");
    }
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <p className="eg-breadcrumb">HOME / CAMERAS</p>
          <h1 className="eg-page-title">Cameras</h1>
          <p className="eg-page-desc">Manage physical camera devices for examination halls</p>
        </div>

        <div className="eg-filter-bar">
          <input
            type="text"
            placeholder="Search cameras..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            className="eg-input flex-1"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="eg-select"
          >
            <option value="">All Statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
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
            + Add Camera
          </button>
        </div>

        {error && (
          <div className="eg-alert eg-alert-danger mb-6">
            {error}
          </div>
        )}

        {loading ? (
          <div className="eg-empty">
            <p className="eg-empty-title">Loading cameras...</p>
          </div>
        ) : cameras.length === 0 ? (
          <div className="eg-empty">
            <p className="eg-empty-title">No cameras configured</p>
            <p className="eg-empty-desc">Get started by adding your first camera.</p>
            <button onClick={openCreate} className="eg-btn eg-btn-primary mt-4">
              + Add Camera
            </button>
          </div>
        ) : (
          <>
            <div className="eg-table-wrap">
              <table className="eg-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Identifier</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Last Seen</th>
                    <th>Hall</th>
                    <th>Active</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cameras.map((c) => (
                    <tr key={c.id}>
                      <td>{c.name}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>
                        {c.device_identifier}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>
                        {c.camera_type || "—"}
                      </td>
                      <td>
                        <span
                          className={`eg-badge ${
                            c.status === "ONLINE"
                              ? "eg-badge-success"
                              : c.status === "DISABLED"
                                ? "eg-badge-danger"
                                : "eg-badge-neutral"
                          }`}
                        >
                          {c.status}
                        </span>
                        {c.health_reason && (
                          <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginTop: "2px" }}>
                            {healthReasonLabel(c.health_reason)}
                          </div>
                        )}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        {formatTimestamp(c.last_seen_at)}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>
                        {hallLabel(c.exam_hall_id)}
                      </td>
                      <td>
                        <span
                          className={`eg-badge ${c.is_active ? "eg-badge-success" : "eg-badge-danger"}`}
                        >
                          {c.is_active ? "Yes" : "No"}
                        </span>
                      </td>
                      <td className="text-right">
                        <button onClick={() => openEdit(c)} className="eg-btn text-xs mr-4">
                          Edit
                        </button>
                        {c.is_active && (
                          <button
                            onClick={() => setConfirmDelete(c.id)}
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
                  {editCamera ? "Edit Camera" : "Add Camera"}
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
                    placeholder="e.g. Main Hall Camera 1"
                  />
                </div>
                <div className="eg-field">
                  <label className="eg-label">Device Identifier *</label>
                  <input
                    type="text"
                    required
                    value={form.device_identifier}
                    onChange={(e) => setForm((f) => ({ ...f, device_identifier: e.target.value }))}
                    className="eg-input w-full"
                    style={{ fontFamily: "var(--font-mono)" }}
                    placeholder="e.g. CAM-001"
                  />
                </div>
                <div className="eg-grid-2">
                  <div className="eg-field">
                    <label className="eg-label">Camera Type</label>
                    <input
                      type="text"
                      value={form.camera_type || ""}
                      onChange={(e) => setForm((f) => ({ ...f, camera_type: e.target.value || null }))}
                      className="eg-input w-full"
                      placeholder="e.g. IP, USB"
                    />
                  </div>
                  <div className="eg-field">
                    <label className="eg-label">Manufacturer</label>
                    <input
                      type="text"
                      value={form.manufacturer || ""}
                      onChange={(e) => setForm((f) => ({ ...f, manufacturer: e.target.value || null }))}
                      className="eg-input w-full"
                      placeholder="e.g. Hikvision"
                    />
                  </div>
                </div>
                <div className="eg-grid-2">
                  <div className="eg-field">
                    <label className="eg-label">Model Name</label>
                    <input
                      type="text"
                      value={form.model_name || ""}
                      onChange={(e) => setForm((f) => ({ ...f, model_name: e.target.value || null }))}
                      className="eg-input w-full"
                      placeholder="e.g. DS-2CD2143"
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
                <div className="eg-grid-2">
                  <div className="eg-field">
                    <label className="eg-label">Resolution Width</label>
                    <input
                      type="number"
                      min="1"
                      value={form.resolution_width || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          resolution_width: e.target.value ? Number(e.target.value) : null,
                        }))
                      }
                      className="eg-input w-full"
                      placeholder="px"
                    />
                  </div>
                  <div className="eg-field">
                    <label className="eg-label">Resolution Height</label>
                    <input
                      type="number"
                      min="1"
                      value={form.resolution_height || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          resolution_height: e.target.value ? Number(e.target.value) : null,
                        }))
                      }
                      className="eg-input w-full"
                      placeholder="px"
                    />
                  </div>
                </div>
                <div className="eg-field">
                  <label className="eg-label">Connection Info</label>
                  <input
                    type="text"
                    value={form.connection_info || ""}
                    onChange={(e) => setForm((f) => ({ ...f, connection_info: e.target.value || null }))}
                    className="eg-input w-full"
                    style={{ fontFamily: "var(--font-mono)" }}
                    placeholder="IP address or endpoint URL"
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button type="submit" disabled={formLoading} className="eg-btn eg-btn-primary">
                    {formLoading ? "Saving..." : editCamera ? "Update Camera" : "Create Camera"}
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
              <h2 className="eg-page-title text-lg mb-4">Deactivate Camera</h2>
              <p className="eg-body mb-6">
                This will deactivate the camera. It will no longer appear in active operations.
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
