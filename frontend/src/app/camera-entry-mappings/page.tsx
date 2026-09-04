"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <Link
          href="/dashboard"
          className="text-[#999] hover:text-white text-sm mb-6 inline-block"
        >
          &larr; BACK TO DASHBOARD
        </Link>

        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold uppercase tracking-wider">
              Camera ↔ Entry Point Mappings
            </h1>
            <p className="text-[#999] mt-1">
              Associate cameras with examination entry points
            </p>
          </div>
          <button
            onClick={() => {
              setShowForm(true);
              setFormError("");
              setSelectedCamera("");
              setSelectedEP("");
            }}
            className="bg-white text-black px-4 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors"
          >
            + Create Mapping
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-6">
          <label className="flex items-center gap-2 text-sm text-[#999] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showDisabled}
              onChange={(e) => {
                setShowDisabled(e.target.checked);
                setPage(1);
              }}
              className="accent-white"
            />
            INCLUDE DISABLED
          </label>
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-500/30 text-red-400 px-4 py-3 mb-6 font-mono text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-20 text-[#666] font-mono text-sm uppercase">
            Loading mappings...
          </div>
        ) : mappings.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-[#666] font-mono text-sm uppercase mb-4">
              No camera mappings configured
            </p>
            <button
              onClick={() => {
                setShowForm(true);
                setFormError("");
              }}
              className="bg-white text-black px-4 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors"
            >
              + Create Mapping
            </button>
          </div>
        ) : (
          <>
            <div className="bg-[#111] border border-white/10 overflow-hidden">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-white/10 text-xs text-[#999] uppercase tracking-wider">
                    <th className="px-4 py-3 font-mono">Camera</th>
                    <th className="px-4 py-3 font-mono">Entry Point</th>
                    <th className="px-4 py-3 font-mono">Hall</th>
                    <th className="px-4 py-3 font-mono">Enabled</th>
                    <th className="px-4 py-3 font-mono">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {mappings.map((m) => (
                    <tr
                      key={m.id}
                      className="border-b border-white/5 hover:bg-white/[0.02]"
                    >
                      <td className="px-4 py-3">
                        <div className="text-sm">{cameraName(m.camera_id)}</div>
                        <div className="text-xs text-[#666] font-mono">
                          {cameraIdentifier(m.camera_id)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-sm">
                          {entryPointName(m.entry_point_id)}
                        </div>
                        <div className="text-xs text-[#666] font-mono">
                          {entryPointCode(m.entry_point_id)}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-[#999]">
                        {hallLabel(cameraHallId(m.camera_id))}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs font-mono ${
                            m.is_enabled
                              ? "text-emerald-400"
                              : "text-red-400"
                          }`}
                        >
                          {m.is_enabled ? "YES" : "NO"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {m.is_enabled && (
                          <button
                            onClick={() => setConfirmDelete(m.id)}
                            className="text-[#999] hover:text-red-400 text-xs font-mono uppercase"
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

            {/* Pagination */}
            <div className="flex items-center justify-between mt-4">
              <p className="text-xs text-[#666] font-mono">
                {total} TOTAL &middot; PAGE {page} OF {totalPages || 1}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="border border-white/20 px-3 py-1 text-xs font-mono uppercase disabled:opacity-30 hover:bg-white/5"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="border border-white/20 px-3 py-1 text-xs font-mono uppercase disabled:opacity-30 hover:bg-white/5"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}

        {/* Create Mapping Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-[#111] border border-white/10 w-full max-w-lg">
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                <h2 className="text-lg font-mono uppercase tracking-wider">
                  Create Mapping
                </h2>
                <button
                  onClick={() => setShowForm(false)}
                  className="text-[#666] hover:text-white text-xl"
                >
                  &times;
                </button>
              </div>
              <form onSubmit={handleCreate} className="p-6 space-y-4">
                {formError && (
                  <div className="bg-red-900/20 border border-red-500/30 text-red-400 px-3 py-2 text-sm font-mono">
                    {formError}
                  </div>
                )}
                <div>
                  <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                    Camera *
                  </label>
                  {activeCameras.length === 0 ? (
                    <p className="text-sm text-[#666] font-mono">
                      No active cameras available
                    </p>
                  ) : (
                    <select
                      required
                      value={selectedCamera}
                      onChange={(e) =>
                        setSelectedCamera(
                          e.target.value ? Number(e.target.value) : ""
                        )
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
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
                <div>
                  <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                    Entry Point *
                  </label>
                  {activeEPs.length === 0 ? (
                    <p className="text-sm text-[#666] font-mono">
                      No active entry points available
                    </p>
                  ) : (
                    <select
                      required
                      value={selectedEP}
                      onChange={(e) =>
                        setSelectedEP(
                          e.target.value ? Number(e.target.value) : ""
                        )
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
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
                    className="bg-white text-black px-6 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] disabled:opacity-50 transition-colors"
                  >
                    {formLoading ? "CREATING..." : "CREATE MAPPING"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className="border border-white/20 px-6 py-2 font-mono text-sm uppercase text-[#999] hover:bg-white/5"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Disable Confirmation */}
        {confirmDelete !== null && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-[#111] border border-white/10 w-full max-w-sm p-6">
              <h2 className="text-lg font-mono uppercase tracking-wider mb-4">
                Disable Mapping
              </h2>
              <p className="text-sm text-[#999] mb-6">
                This will disable the camera-to-entry-point association.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleDeactivate(confirmDelete)}
                  className="bg-red-900/50 border border-red-500/30 text-red-400 px-4 py-2 font-mono text-sm uppercase hover:bg-red-900/80 transition-colors"
                >
                  Disable
                </button>
                <button
                  onClick={() => setConfirmDelete(null)}
                  className="border border-white/20 px-4 py-2 font-mono text-sm uppercase text-[#999] hover:bg-white/5"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
