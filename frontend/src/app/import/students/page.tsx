"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import {
  parseSpreadsheet,
  generateTemplate,
  validateRows,
  exportFailedRows,
  type ValidationError,
} from "@/lib/spreadsheet";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_STUDENTS = 500;

const HEADERS = ["USN", "Name"];
const REQUIRED_COLUMNS = ["USN", "Name"];

interface StudentItem {
  usn: string;
  name: string;
}

interface ImportResult {
  usn: string;
  status: string;
  error?: string;
}

interface ImportResponse {
  total: number;
  created: number;
  skipped: number;
  failed: number;
  results: ImportResult[];
}

type Phase = "select" | "preview" | "submitting" | "result";

interface RowState {
  row: Record<string, unknown>;
  errors: ValidationError[];
  valid: boolean;
}

export default function ImportStudentsPage() {
  const [phase, setPhase] = useState<Phase>("select");
  const [rows, setRows] = useState<RowState[]>([]);
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<ImportResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const validCount = rows.filter((r) => r.valid).length;
  const invalidCount = rows.filter((r) => !r.valid).length;

  const reset = useCallback(() => {
    setPhase("select");
    setRows([]);
    setParseError("");
    setResponse(null);
    setSubmitError("");
    if (fileRef.current) fileRef.current.value = "";
  }, []);

  const handleFile = useCallback(async (file: File) => {
    setParseError("");
    setRows([]);

    try {
      const { rows: data } = await parseSpreadsheet(file);

      if (data.length === 0) {
        setParseError("File contains no data rows");
        return;
      }

      if (data.length > MAX_STUDENTS) {
        setParseError(
          `File contains ${data.length} rows, maximum is ${MAX_STUDENTS}`
        );
        return;
      }

      const result = validateRows<StudentItem>(
        data,
        REQUIRED_COLUMNS,
        (row) => {
          const errors: ValidationError[] = [];
          const usn = String(row["USN"] ?? "").trim();
          if (usn.length > 20) {
            errors.push({
              row: 0,
              column: "USN",
              message: "USN must be 20 characters or fewer",
            });
          }
          const name = String(row["Name"] ?? "").trim();
          if (name.length > 255) {
            errors.push({
              row: 0,
              column: "Name",
              message: "Name must be 255 characters or fewer",
            });
          }
          return errors;
        },
        (row) => ({
          usn: String(row["USN"] ?? "").trim(),
          name: String(row["Name"] ?? "").trim(),
        })
      );

      const rowStates = data.map((row, i) => {
        const found = result.allRows[i];
        return found ?? { row, errors: [], valid: true };
      });

      setRows(rowStates);
      setPhase("preview");
    } catch (err) {
      setParseError(
        err instanceof Error ? err.message : "Failed to parse file"
      );
    }
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
    setPhase("submitting");
    setSubmitError("");

    const validStudents: StudentItem[] = rows
      .filter((r) => r.valid)
      .map((r) => ({
        usn: String(r.row["USN"] ?? "").trim(),
        name: String(r.row["Name"] ?? "").trim(),
      }));

    try {
      const res = await fetch(`${API}/api/v1/import/students`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ students: validStudents }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data: ImportResponse = await res.json();
      setResponse(data);
      setPhase("result");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Import failed");
      setPhase("preview");
    }
  };

  const handleDownloadTemplate = () => {
    generateTemplate(
      HEADERS,
      [["CS001", "John Doe"], ["CS002", "Jane Smith"]],
      [
        { column: "USN", description: "University Seat Number (required, max 20 characters)" },
        { column: "Name", description: "Full name of the student (required, max 255 characters)" },
      ],
      "Students"
    );
  };

  const handleExportFailed = () => {
    const failed = rows.filter((r) => !r.valid);
    exportFailedRows(
      failed.map((f) => ({ row: f.row, errors: f.errors })),
      HEADERS
    );
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Import Students
        </h1>
        <p className="text-[#999] mb-8">
          Upload an Excel or CSV file to bulk import student records (max{" "}
          {MAX_STUDENTS})
        </p>

        {phase === "select" && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">How to import</h2>
              <ol className="text-sm text-[#999] space-y-2 list-decimal list-inside">
                <li>
                  Download the template file using the button below
                </li>
                <li>
                  Fill in the student data in Excel or Google Sheets
                </li>
                <li>
                  Save as .xlsx or .csv and upload the file
                </li>
                <li>
                  Review the preview and click Import
                </li>
              </ol>
              <button
                onClick={handleDownloadTemplate}
                className="mt-4 border border-cyan-500/50 text-cyan-400 px-4 py-2 rounded-lg text-sm hover:bg-cyan-500/10 transition-colors"
              >
                Download Template
              </button>
            </div>

            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="border-2 border-dashed border-white/20 rounded-lg p-16 text-center hover:border-white/40 transition-colors cursor-pointer"
              onClick={() => fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFile(file);
                }}
              />
              <p className="text-[#999] text-lg mb-2">
                Drop an Excel or CSV file here
              </p>
              <p className="text-[#666] text-sm">
                Accepts .xlsx and .csv files
              </p>
            </div>
          </div>
        )}

        {parseError && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg p-4 mb-6">
            <p className="text-pink-400 text-sm">{parseError}</p>
          </div>
        )}

        {phase === "preview" && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex gap-6 text-sm">
                  <span className="text-[#999]">
                    <span className="text-white font-medium">{rows.length}</span>{" "}
                    total rows
                  </span>
                  {validCount > 0 && (
                    <span className="text-emerald-400">
                      {validCount} valid
                    </span>
                  )}
                  {invalidCount > 0 && (
                    <span className="text-pink-400">
                      {invalidCount} with errors
                    </span>
                  )}
                </div>
                <div className="flex gap-3">
                  {invalidCount > 0 && (
                    <button
                      onClick={handleExportFailed}
                      className="border border-white/20 px-4 py-2 rounded-lg text-sm hover:bg-white/5"
                    >
                      Export Failed Rows
                    </button>
                  )}
                  <button
                    onClick={reset}
                    className="border border-white/20 px-4 py-2 rounded-lg text-sm hover:bg-white/5"
                  >
                    Cancel
                  </button>
                  {validCount > 0 && (
                    <button
                      onClick={handleSubmit}
                      className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
                    >
                      Import {validCount} Student{validCount !== 1 ? "s" : ""}
                    </button>
                  )}
                </div>
              </div>
            </div>

            {invalidCount > 0 && (
              <div className="mb-6">
                <h2 className="text-lg font-semibold mb-3 text-pink-400">
                  Rows With Errors ({invalidCount})
                </h2>
                <div className="bg-[#111] border border-pink-500/30 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                        <th className="px-6 py-3">Row</th>
                        <th className="px-6 py-3">USN</th>
                        <th className="px-6 py-3">Name</th>
                        <th className="px-6 py-3">Errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows
                        .filter((r) => !r.valid)
                        .map((r, i) => (
                          <tr
                            key={i}
                            className="border-b border-white/5 hover:bg-white/[0.02]"
                          >
                            <td className="px-6 py-3 text-sm text-[#666]">
                              {rows.indexOf(r) + 1}
                            </td>
                            <td className="px-6 py-3 font-mono text-sm">
                              {String(r.row["USN"] ?? "")}
                            </td>
                            <td className="px-6 py-3 text-sm">
                              {String(r.row["Name"] ?? "")}
                            </td>
                            <td className="px-6 py-3 text-sm text-pink-400">
                              {r.errors.map((e) => e.message).join("; ")}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {validCount > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-3 text-emerald-400">
                  Valid Rows ({validCount})
                </h2>
                <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                        <th className="px-6 py-3">Row</th>
                        <th className="px-6 py-3">USN</th>
                        <th className="px-6 py-3">Name</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows
                        .filter((r) => r.valid)
                        .map((r, i) => (
                          <tr
                            key={i}
                            className="border-b border-white/5 hover:bg-white/[0.02]"
                          >
                            <td className="px-6 py-3 text-sm text-[#666]">
                              {rows.indexOf(r) + 1}
                            </td>
                            <td className="px-6 py-3 font-mono text-sm">
                              {String(r.row["USN"] ?? "")}
                            </td>
                            <td className="px-6 py-3 text-sm">
                              {String(r.row["Name"] ?? "")}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {phase === "submitting" && (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-[#999]">Importing students...</p>
          </div>
        )}

        {phase === "result" && response && (
          <div>
            <div className="grid grid-cols-4 gap-4 mb-6">
              {[
                { label: "Total", value: response.total, color: "text-white" },
                { label: "Created", value: response.created, color: "text-emerald-400" },
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
                      <th className="px-6 py-3">USN</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.results.map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-3 font-mono text-sm">{r.usn}</td>
                        <td className="px-6 py-3">
                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              r.status === "created"
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
                          {r.error || "\u2014"}
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
