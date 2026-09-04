"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
              Cameras
            </h1>
            <p className="text-[#999] mt-1">
              Manage physical camera devices for examination halls
            </p>
          </div>
          <button
            onClick={openCreate}
            className="bg-white text-black px-4 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors"
          >
            + Add Camera
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-6">
          <input
            type="text"
            placeholder="SEARCH CAMERAS..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            className="flex-1 bg-[#111] border border-white/10 px-4 py-2 text-white placeholder:text-[#666] focus:outline-none focus:border-white/30 font-mono text-sm uppercase"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[#111] border border-white/10 px-4 py-2 text-white focus:outline-none focus:border-white/30 font-mono text-sm uppercase"
          >
            <option value="">ALL STATUSES</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-[#999] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => {
                setShowInactive(e.target.checked);
                setPage(1);
              }}
              className="accent-white"
            />
            INCLUDE INACTIVE
          </label>
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-500/30 text-red-400 px-4 py-3 mb-6 font-mono text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-20 text-[#666] font-mono text-sm uppercase">
            Loading cameras...
          </div>
        ) : cameras.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-[#666] font-mono text-sm uppercase mb-4">
              No cameras configured
            </p>
            <button
              onClick={openCreate}
              className="bg-white text-black px-4 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors"
            >
              + Add Camera
            </button>
          </div>
        ) : (
          <>
            <div className="bg-[#111] border border-white/10 overflow-hidden">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-white/10 text-xs text-[#999] uppercase tracking-wider">
                    <th className="px-4 py-3 font-mono">Name</th>
                    <th className="px-4 py-3 font-mono">Identifier</th>
                    <th className="px-4 py-3 font-mono">Type</th>
                    <th className="px-4 py-3 font-mono">Status</th>
                    <th className="px-4 py-3 font-mono">Hall</th>
                    <th className="px-4 py-3 font-mono">Active</th>
                    <th className="px-4 py-3 font-mono">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cameras.map((c) => (
                    <tr
                      key={c.id}
                      className="border-b border-white/5 hover:bg-white/[0.02]"
                    >
                      <td className="px-4 py-3 text-sm">{c.name}</td>
                      <td className="px-4 py-3 text-sm font-mono text-[#999]">
                        {c.device_identifier}
                      </td>
                      <td className="px-4 py-3 text-sm text-[#999]">
                        {c.camera_type || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs font-mono uppercase ${
                            c.status === "ONLINE"
                              ? "text-emerald-400"
                              : c.status === "DISABLED"
                                ? "text-red-400"
                                : "text-[#999]"
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-[#999]">
                        {hallLabel(c.exam_hall_id)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs font-mono ${
                            c.is_active ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {c.is_active ? "YES" : "NO"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm space-x-3">
                        <button
                          onClick={() => openEdit(c)}
                          className="text-[#999] hover:text-white text-xs font-mono uppercase"
                        >
                          Edit
                        </button>
                        {c.is_active && (
                          <button
                            onClick={() => setConfirmDelete(c.id)}
                            className="text-[#999] hover:text-red-400 text-xs font-mono uppercase"
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

        {/* Create/Edit Form Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-[#111] border border-white/10 w-full max-w-lg max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                <h2 className="text-lg font-mono uppercase tracking-wider">
                  {editCamera ? "Edit Camera" : "Add Camera"}
                </h2>
                <button
                  onClick={() => setShowForm(false)}
                  className="text-[#666] hover:text-white text-xl"
                >
                  &times;
                </button>
              </div>
              <form onSubmit={handleSubmit} className="p-6 space-y-4">
                {formError && (
                  <div className="bg-red-900/20 border border-red-500/30 text-red-400 px-3 py-2 text-sm font-mono">
                    {formError}
                  </div>
                )}
                <div>
                  <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, name: e.target.value }))
                    }
                    className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                    placeholder="e.g. Main Hall Camera 1"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                    Device Identifier *
                  </label>
                  <input
                    type="text"
                    required
                    value={form.device_identifier}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        device_identifier: e.target.value,
                      }))
                    }
                    className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-white/30"
                    placeholder="e.g. CAM-001"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                      Camera Type
                    </label>
                    <input
                      type="text"
                      value={form.camera_type || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          camera_type: e.target.value || null,
                        }))
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                      placeholder="e.g. IP, USB"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                      Manufacturer
                    </label>
                    <input
                      type="text"
                      value={form.manufacturer || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          manufacturer: e.target.value || null,
                        }))
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                      placeholder="e.g. Hikvision"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                      Model Name
                    </label>
                    <input
                      type="text"
                      value={form.model_name || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          model_name: e.target.value || null,
                        }))
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                      placeholder="e.g. DS-2CD2143"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                      Exam Hall
                    </label>
                    <select
                      value={form.exam_hall_id || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          exam_hall_id: e.target.value
                            ? Number(e.target.value)
                            : null,
                        }))
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
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
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                      Resolution Width
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={form.resolution_width || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          resolution_width: e.target.value
                            ? Number(e.target.value)
                            : null,
                        }))
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                      placeholder="px"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                      Resolution Height
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={form.resolution_height || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          resolution_height: e.target.value
                            ? Number(e.target.value)
                            : null,
                        }))
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                      placeholder="px"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                    Connection Info
                  </label>
                  <input
                    type="text"
                    value={form.connection_info || ""}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        connection_info: e.target.value || null,
                      }))
                    }
                    className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-white/30"
                    placeholder="IP address or endpoint URL"
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    type="submit"
                    disabled={formLoading}
                    className="bg-white text-black px-6 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] disabled:opacity-50 transition-colors"
                  >
                    {formLoading
                      ? "SAVING..."
                      : editCamera
                        ? "UPDATE CAMERA"
                        : "CREATE CAMERA"}
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

        {/* Deactivate Confirmation */}
        {confirmDelete !== null && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-[#111] border border-white/10 w-full max-w-sm p-6">
              <h2 className="text-lg font-mono uppercase tracking-wider mb-4">
                Deactivate Camera
              </h2>
              <p className="text-sm text-[#999] mb-6">
                This will deactivate the camera. It will no longer appear in
                active operations.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleDeactivate(confirmDelete)}
                  className="bg-red-900/50 border border-red-500/30 text-red-400 px-4 py-2 font-mono text-sm uppercase hover:bg-red-900/80 transition-colors"
                >
                  Deactivate
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
