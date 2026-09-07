"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getInvigilatorDashboard,
  startExam,
  endExam,
  type InvigilatorDashboard,
} from "../../lib/invigilator-api";
import { ApiError } from "../../lib/api";

export default function InvigilatorPage() {
  const [data, setData] = useState<InvigilatorDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const dash = await getInvigilatorDashboard();
      setData(dash);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to load dashboard";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleStart = async () => {
    try {
      setActionLoading(true);
      setActionMsg(null);
      const res = await startExam();
      setActionMsg(`Exam started. Session ${res.session_id}`);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to start exam";
      setActionMsg(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleEnd = async () => {
    try {
      setActionLoading(true);
      setActionMsg(null);
      const res = await endExam();
      setActionMsg(`Exam ended. Session ${res.session_id}`);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : "Failed to end exam";
      setActionMsg(msg);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-lg">Loading invigilator dashboard...</div>;
  if (error) return <div className="p-8 text-center text-red-600">Error: {error}</div>;
  if (!data) return <div className="p-8 text-center">No data</div>;

  const { profile: p } = data;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Invigilator Control Center</h1>

      {/* Profile card */}
      <div className="eg-panel p-4 space-y-2">
        <div className="text-sm opacity-60">Logged in as</div>
        <div className="font-medium">{p.full_name || p.email}</div>
        <div className="text-sm opacity-60">{p.email}</div>
      </div>

      {/* Exam info */}
      <div className="eg-panel p-4 space-y-3">
        <h2 className="text-lg font-semibold">Assigned Examination</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><span className="opacity-60">Exam:</span> {p.exam_name}</div>
          <div><span className="opacity-60">Subject:</span> {p.subject_code} — {p.subject_name}</div>
          <div><span className="opacity-60">Date:</span> {p.exam_date}</div>
          <div><span className="opacity-60">Time:</span> {p.exam_start_time} — {p.exam_end_time}</div>
          <div><span className="opacity-60">Hall:</span> {p.hall_name} ({p.hall_building} {p.hall_room})</div>
          <div><span className="opacity-60">Entry Point:</span> {p.entry_point_name || "Not assigned"} ({p.entry_point_code || "N/A"})</div>
          <div><span className="opacity-60">Camera:</span> {p.camera_name || "Not assigned"} ({p.camera_status || "N/A"})</div>
          <div><span className="opacity-60">Session Status:</span> {p.session_status || "No session"}</div>
          <div><span className="opacity-60">Gate Status:</span> {p.gate_status || "N/A"}</div>
        </div>
      </div>

      {/* Controls */}
      <div className="eg-panel p-4 space-y-3">
        <h2 className="text-lg font-semibold">Session Controls</h2>
        <div className="flex gap-3">
          <button
            onClick={handleStart}
            disabled={!data.can_start || actionLoading}
            className="px-4 py-2 rounded bg-green-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {actionLoading ? "Starting..." : "Start Exam"}
          </button>
          <button
            onClick={handleEnd}
            disabled={!data.can_end || actionLoading}
            className="px-4 py-2 rounded bg-red-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {actionLoading ? "Ending..." : "End Exam"}
          </button>
          <button
            onClick={load}
            disabled={actionLoading}
            className="px-4 py-2 rounded border border-white/20"
          >
            Refresh
          </button>
        </div>
        {actionMsg && <div className="text-sm mt-2 p-2 rounded bg-black/20">{actionMsg}</div>}
        {!data.can_start && !data.can_end && p.session_status !== "IN_PROGRESS" && (
          <div className="text-sm opacity-60">
            Exam is not within the permitted start window. Start is allowed 15 minutes before the scheduled time.
          </div>
        )}
      </div>

      {/* Live stats */}
      <div className="eg-panel p-4 space-y-3">
        <h2 className="text-lg font-semibold">Live Statistics</h2>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="p-3 rounded bg-green-500/10">
            <div className="text-2xl font-bold text-green-400">{data.granted_count}</div>
            <div className="text-xs opacity-60">Verified</div>
          </div>
          <div className="p-3 rounded bg-red-500/10">
            <div className="text-2xl font-bold text-red-400">{data.denied_count}</div>
            <div className="text-xs opacity-60">Denied</div>
          </div>
          <div className="p-3 rounded bg-yellow-500/10">
            <div className="text-2xl font-bold text-yellow-400">{data.escalated_count}</div>
            <div className="text-xs opacity-60">Review</div>
          </div>
          <div className="p-3 rounded bg-blue-500/10">
            <div className="text-2xl font-bold text-blue-400">{data.attendance_count}</div>
            <div className="text-xs opacity-60">Attendance</div>
          </div>
          <div className="p-3 rounded bg-orange-500/10">
            <div className="text-2xl font-bold text-orange-400">{data.security_event_count}</div>
            <div className="text-xs opacity-60">Security Events</div>
          </div>
          <div className="p-3 rounded bg-white/5">
            <div className="text-2xl font-bold">{data.verification_count}</div>
            <div className="text-xs opacity-60">Total Verifications</div>
          </div>
        </div>
      </div>

      {/* Recent verifications */}
      {data.recent_verifications.length > 0 && (
        <div className="eg-panel p-4 space-y-3">
          <h2 className="text-lg font-semibold">Recent Verifications</h2>
          <div className="space-y-2">
            {data.recent_verifications.map((v: Record<string, unknown>) => (
              <div key={v.id as number} className="flex items-center gap-3 text-sm p-2 rounded bg-black/10">
                <span className="font-mono text-xs opacity-50">#{v.id as number}</span>
                <span className="opacity-60">Student {v.student_id as number}</span>
                <span className={`px-2 py-0.5 rounded text-xs ${
                  v.status === "GRANTED" ? "bg-green-500/20 text-green-300" :
                  v.status === "DENIED" ? "bg-red-500/20 text-red-300" :
                  "bg-yellow-500/20 text-yellow-300"
                }`}>
                  {v.status as string}
                </span>
                <span className="text-xs opacity-40">{v.created_at as string}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
