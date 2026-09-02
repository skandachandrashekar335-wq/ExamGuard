"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_ASSIGNMENTS = 200;

interface HallOption {
  id: number;
  building: string;
  room_number: string;
  name: string | null;
  capacity: number;
}

interface SeatItem {
  exam_registration_id: number;
  seat_number: string;
  row_number?: number;
  column_number?: number;
}

interface AssignmentResult {
  exam_registration_id: number;
  seat_number: string;
  status: string;
  assignment_id?: number;
  error?: string;
}

interface AssignmentResponse {
  total: number;
  assigned: number;
  skipped: number;
  failed: number;
  results: AssignmentResult[];
}

interface CancelResult {
  assignment_id: number;
  status: string;
  error?: string;
}

interface CancelResponse {
  total: number;
  cancelled: number;
  skipped: number;
  failed: number;
  results: CancelResult[];
}

type Phase = "select" | "preview" | "submitting" | "result";

export default function ImportSeatAssignmentsPage() {
  const [halls, setHalls] = useState<HallOption[]>([]);
  const [selectedHallId, setSelectedHallId] = useState<number | null>(null);
  const [phase, setPhase] = useState<Phase>("select");
  const [assignments, setAssignments] = useState<SeatItem[]>([]);
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<AssignmentResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API}/api/v1/exam-halls?page=1&page_size=100`)
      .then((r) => r.json())
      .then((data) => setHalls(data.items || []))
      .catch(() => {});
  }, []);

  const reset = useCallback(() => {
    setPhase("select");
    setAssignments([]);
    setParseError("");
    setResponse(null);
    setSubmitError("");
    if (fileRef.current) fileRef.current.value = "";
  }, []);

  const handleFile = useCallback((file: File) => {
    setParseError("");

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result as string);

        if (!Array.isArray(data)) {
          setParseError("JSON must be an array of assignment objects");
          return;
        }

        if (data.length === 0) {
          setParseError("File contains no assignments");
          return;
        }

        if (data.length > MAX_ASSIGNMENTS) {
          setParseError(
            `File contains ${data.length} assignments, maximum is ${MAX_ASSIGNMENTS}`
          );
          return;
        }

        for (const item of data) {
          if (
            !item.exam_registration_id ||
            typeof item.exam_registration_id !== "number" ||
            !item.seat_number ||
            typeof item.seat_number !== "string"
          ) {
            setParseError(
              "Each assignment must have 'exam_registration_id' (number) and 'seat_number' (string)"
            );
            return;
          }
        }

        setAssignments(data as SeatItem[]);
        setPhase("preview");
      } catch {
        setParseError("Invalid JSON file");
      }
    };
    reader.readAsText(file);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleSubmit = async () => {
    if (!selectedHallId) return;
    setPhase("submitting");
    setSubmitError("");

    try {
      const res = await fetch(`${API}/api/v1/import/seat-assignments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exam_hall_id: selectedHallId,
          assignments,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data: AssignmentResponse = await res.json();
      setResponse(data);
      setPhase("result");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Import failed");
      setPhase("preview");
    }
  };

  const selectedHall = halls.find((h) => h.id === selectedHallId);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Import Seat Assignments
        </h1>
        <p className="text-[#999] mb-8">
          Bulk assign seats in an exam hall (max {MAX_ASSIGNMENTS} per batch)
        </p>

        {phase === "select" && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Select Exam Hall</h2>
              <select
                value={selectedHallId ?? ""}
                onChange={(e) =>
                  setSelectedHallId(
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="w-full bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              >
                <option value="">Choose an exam hall...</option>
                {halls.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.building} — Room {h.room_number}
                    {h.name ? ` (${h.name})` : ""} — Cap: {h.capacity}
                  </option>
                ))}
              </select>
            </div>

            {selectedHallId && (
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="border-2 border-dashed border-white/20 rounded-lg p-16 text-center hover:border-white/40 transition-colors cursor-pointer"
                onClick={() => fileRef.current?.click()}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".json"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFile(file);
                  }}
                />
                <p className="text-[#999] text-lg mb-2">
                  Drop a JSON file with assignments or click to select
                </p>
                <p className="text-[#666] text-sm">
                  Format: [{"{"} "exam_registration_id": N, "seat_number": "A1" {"}"}]
                </p>
              </div>
            )}
          </div>
        )}

        {parseError && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg p-4 mb-6">
            <p className="text-pink-400 text-sm">{parseError}</p>
          </div>
        )}

        {phase === "preview" && selectedHall && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-4 mb-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#999]">
                    Hall:{" "}
                    <span className="text-white">
                      {selectedHall.building} — Room {selectedHall.room_number}
                    </span>
                  </p>
                  <p className="text-sm text-[#999]">
                    <span className="text-white font-medium">
                      {assignments.length}
                    </span>{" "}
                    assignment{assignments.length !== 1 ? "s" : ""} ready
                  </p>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={reset}
                    className="border border-white/20 px-4 py-2 rounded-lg text-sm hover:bg-white/5"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSubmit}
                    className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
                  >
                    Assign {assignments.length} Seat{assignments.length !== 1 ? "s" : ""}
                  </button>
                </div>
              </div>
            </div>

            <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                    <th className="px-6 py-3">#</th>
                    <th className="px-6 py-3">Registration ID</th>
                    <th className="px-6 py-3">Seat Number</th>
                    <th className="px-6 py-3">Row</th>
                    <th className="px-6 py-3">Column</th>
                  </tr>
                </thead>
                <tbody>
                  {assignments.map((a, i) => (
                    <tr
                      key={i}
                      className="border-b border-white/5 hover:bg-white/[0.02]"
                    >
                      <td className="px-6 py-3 text-sm text-[#666]">{i + 1}</td>
                      <td className="px-6 py-3 font-mono text-sm">
                        {a.exam_registration_id}
                      </td>
                      <td className="px-6 py-3 font-mono text-sm">
                        {a.seat_number}
                      </td>
                      <td className="px-6 py-3 text-sm text-[#999]">
                        {a.row_number ?? "—"}
                      </td>
                      <td className="px-6 py-3 text-sm text-[#999]">
                        {a.column_number ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {phase === "submitting" && (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-[#999]">Assigning seats...</p>
          </div>
        )}

        {phase === "result" && response && (
          <div>
            <div className="grid grid-cols-4 gap-4 mb-6">
              {[
                { label: "Total", value: response.total, color: "text-white" },
                { label: "Assigned", value: response.assigned, color: "text-emerald-400" },
                { label: "Skipped", value: response.skipped, color: "text-amber-400" },
                { label: "Failed", value: response.failed, color: "text-pink-400" },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="bg-[#111] border border-white/10 rounded-lg p-4 text-center"
                >
                  <p className={`text-2xl font-bold ${stat.color}`}>
                    {stat.value}
                  </p>
                  <p className="text-[#999] text-sm">{stat.label}</p>
                </div>
              ))}
            </div>

            {response.results.length > 0 && (
              <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden mb-6">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                      <th className="px-6 py-3">Registration ID</th>
                      <th className="px-6 py-3">Seat</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Assignment ID</th>
                      <th className="px-6 py-3">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.results.map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-3 font-mono text-sm">
                          {r.exam_registration_id}
                        </td>
                        <td className="px-6 py-3 font-mono text-sm">
                          {r.seat_number}
                        </td>
                        <td className="px-6 py-3">
                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              r.status === "assigned"
                                ? "bg-emerald-500/20 text-emerald-400"
                                : r.status === "skipped"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-pink-500/20 text-pink-400"
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="px-6 py-3 text-sm text-[#999]">
                          {r.assignment_id ?? "—"}
                        </td>
                        <td className="px-6 py-3 text-sm text-[#999]">
                          {r.error || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <button
              onClick={reset}
              className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
            >
              Import Another Batch
            </button>
          </div>
        )}

        {submitError && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg p-4 mt-4">
            <p className="text-pink-400 text-sm">{submitError}</p>
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
