"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import {
  listMappings,
  createMapping,
  deactivateMapping,
  listCameras,
  listEntryPoints,
  listExamHalls,
  type CameraEntryPointMapping,
  type Camera,
  type EntryPoint,
  type ExamHall,
  ApiError,
} from "@/lib/camera-api";

export default function CameraEntryMappingsPage() {
  const [mappings, setMappings] = useState<CameraEntryPointMapping[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [showDisabled, setShowDisabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [cameras, setCameras] = useState<Camera[]>([]);
  const [entryPoints, setEntryPoints] = useState<EntryPoint[]>([]);
  const [halls, setHalls] = useState<ExamHall[]>([]);

  const [showForm, setShowForm] = useState(false);
  const [selectedCamera, setSelectedCamera] = useState<number | "">("");
  const [selectedEP, setSelectedEP] = useState<number | "">("");
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);

  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  async function loadRefs() {
    try {
      const [c, e, h] = await Promise.all([
        listCameras({ page_size: 100, include_inactive: true }),
        listEntryPoints({ page_size: 100, include_inactive: true }),
        listExamHalls({ page_size: 100, include_inactive: true }),
      ]);
      setCameras(c.items);
      setEntryPoints(e.items);
      setHalls(h.items);
    } catch {
      // Non-critical
    }
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listMappings({
        page,
        page_size: pageSize,
        include_disabled: showDisabled,
      });
      setMappings(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load mappings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, showDisabled]);

  useEffect(() => {
    loadRefs();
  }, []);

  function cameraName(id: number): string {
    const c = cameras.find((c) => c.id === id);
    return c ? c.name : `Camera #${id}`;
  }

  function cameraIdentifier(id: number): string {
    const c = cameras.find((c) => c.id === id);
    return c ? c.device_identifier : "";
  }

  function entryPointName(id: number): string {
    const ep = entryPoints.find((e) => e.id === id);
    return ep ? ep.name : `Entry Point #${id}`;
  }

  function entryPointCode(id: number): string {
    const ep = entryPoints.find((e) => e.id === id);
    return ep ? ep.code : "";
  }

  function hallLabel(id: number | null): string {
    if (!id) return "—";
    const h = halls.find((h) => h.id === id);
    return h ? `${h.building} ${h.room_number}` : `Hall #${id}`;
  }

  function cameraHallId(cameraId: number): number | null {
    const c = cameras.find((c) => c.id === cameraId);
    return c ? c.exam_hall_id : null;
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedCamera || !selectedEP) return;
    setFormLoading(true);
    setFormError("");
    try {
      await createMapping({
        camera_id: Number(selectedCamera),
        entry_point_id: Number(selectedEP),
      });
      setShowForm(false);
      setSelectedCamera("");
      setSelectedEP("");
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
      await deactivateMapping(id);
      setConfirmDelete(null);
      load();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to deactivate mapping"
      );
    }
  }

  const totalPages = Math.ceil(total / pageSize);

  const activeCameras = cameras.filter((c) => c.is_active);
  const activeEPs = entryPoints.filter((ep) => ep.is_active);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <p className="eg-breadcrumb">HOME / CAMERA-ENTRY MAPPINGS</p>
          <h1 className="eg-page-title">Camera ↔ Entry Point Mappings</h1>
          <p className="eg-page-desc">Associate cameras with examination entry points</p>
        </div>

        <div className="eg-filter-bar">
          <label className="eg-label flex items-center gap-2">
            <input
              type="checkbox"
              checked={showDisabled}
              onChange={(e) => {
                setShowDisabled(e.target.checked);
                setPage(1);
              }}
              className="eg-checkbox"
            />
            Include disabled
          </label>
          <button
            onClick={() => {
              setShowForm(true);
              setFormError("");
              setSelectedCamera("");
              setSelectedEP("");
            }}
            className="eg-btn eg-btn-primary"
          >
            + Create Mapping
          </button>
        </div>

        {error && (
          <div className="eg-alert eg-alert-danger mb-6">
            {error}
          </div>
        )}

        {loading ? (
          <div className="eg-empty">
            <p className="eg-empty-title">Loading mappings...</p>
          </div>
        ) : mappings.length === 0 ? (
          <div className="eg-empty">
            <p className="eg-empty-title">No camera mappings configured</p>
            <p className="eg-empty-desc">Create a mapping to associate a camera with an entry point.</p>
            <button
              onClick={() => {
                setShowForm(true);
                setFormError("");
              }}
              className="eg-btn eg-btn-primary mt-4"
            >
              + Create Mapping
            </button>
          </div>
        ) : (
          <>
            <div className="eg-table-wrap">
              <table className="eg-table">
                <thead>
                  <tr>
                    <th>Camera</th>
                    <th>Entry Point</th>
                    <th>Hall</th>
                    <th>Enabled</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {mappings.map((m) => (
                    <tr key={m.id}>
                      <td>
                        <div>{cameraName(m.camera_id)}</div>
                        <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                          {cameraIdentifier(m.camera_id)}
                        </div>
                      </td>
                      <td>
                        <div>{entryPointName(m.entry_point_id)}</div>
                        <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                          {entryPointCode(m.entry_point_id)}
                        </div>
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>
                        {hallLabel(cameraHallId(m.camera_id))}
                      </td>
                      <td>
                        <span
                          className={`eg-badge ${m.is_enabled ? "eg-badge-success" : "eg-badge-danger"}`}
                        >
                          {m.is_enabled ? "Yes" : "No"}
                        </span>
                      </td>
                      <td className="text-right">
                        {m.is_enabled && (
                          <button
                            onClick={() => setConfirmDelete(m.id)}
                            className="eg-btn eg-btn-danger text-xs"
                          >
                            Disable
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
                <h2 className="eg-page-title text-lg">Create Mapping</h2>
                <button onClick={() => setShowForm(false)} className="eg-modal-close">&times;</button>
              </div>
              <form onSubmit={handleCreate} className="eg-modal-body">
                {formError && (
                  <div className="eg-alert eg-alert-danger mb-4">
                    {formError}
                  </div>
                )}
                <div className="eg-field">
                  <label className="eg-label">Camera *</label>
                  {activeCameras.length === 0 ? (
                    <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
                      No active cameras available
                    </p>
                  ) : (
                    <select
                      required
                      value={selectedCamera}
                      onChange={(e) =>
                        setSelectedCamera(e.target.value ? Number(e.target.value) : "")
                      }
                      className="eg-select w-full"
                    >
                      <option value="">Select a camera</option>
                      {activeCameras.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} ({c.device_identifier})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div className="eg-field">
                  <label className="eg-label">Entry Point *</label>
                  {activeEPs.length === 0 ? (
                    <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
                      No active entry points available
                    </p>
                  ) : (
                    <select
                      required
                      value={selectedEP}
                      onChange={(e) =>
                        setSelectedEP(e.target.value ? Number(e.target.value) : "")
                      }
                      className="eg-select w-full"
                    >
                      <option value="">Select an entry point</option>
                      {activeEPs.map((ep) => (
                        <option key={ep.id} value={ep.id}>
                          {ep.name} ({ep.code})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    type="submit"
                    disabled={formLoading || !selectedCamera || !selectedEP}
                    className="eg-btn eg-btn-primary"
                  >
                    {formLoading ? "Creating..." : "Create Mapping"}
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
              <h2 className="eg-page-title text-lg mb-4">Disable Mapping</h2>
              <p className="eg-body mb-6">
                This will disable the camera-to-entry-point association.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleDeactivate(confirmDelete)}
                  className="eg-btn eg-btn-danger"
                >
                  Disable
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
