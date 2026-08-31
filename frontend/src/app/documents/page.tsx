"use client";

import { useEffect, useState } from "react";

interface Document {
  id: number;
  original_filename: string;
  stored_key: string;
  content_type: string;
  file_size: number;
  document_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("HALL_TICKET");

  const fetchDocuments = async () => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: "10",
    });
    const res = await fetch(`${API}/api/v1/documents?${params}`);
    const data = await res.json();
    setDocuments(data.items);
    setTotal(data.total);
  };

  useEffect(() => {
    fetchDocuments();
  }, [page]);

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setMessage("");
    setError("");

    const formData = new FormData();
    formData.append("file", selectedFile);

    const res = await fetch(
      `${API}/api/v1/documents?document_type=${docType}`,
      { method: "POST", body: formData }
    );

    if (res.ok) {
      setMessage("Document uploaded successfully");
      setSelectedFile(null);
      fetchDocuments();
    } else {
      const err = await res.json();
      setError(err.detail || "Upload failed");
    }
    setUploading(false);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const totalPages = Math.ceil(total / 10);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Documents
        </h1>
        <p className="text-[#999] mb-8">Upload and manage examination documents</p>

        <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Upload Document</h2>
          {message && <p className="text-emerald-400 text-sm mb-4">{message}</p>}
          {error && <p className="text-pink-400 text-sm mb-4">{error}</p>}
          <div className="flex gap-4 items-center">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="HALL_TICKET">Hall Ticket</option>
            </select>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="text-sm text-[#999] file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-gradient-to-r file:from-cyan-500 file:to-pink-500 file:text-white file:cursor-pointer"
            />
            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
              className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90 disabled:opacity-30"
            >
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        </div>

        <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                <th className="px-6 py-3">Filename</th>
                <th className="px-6 py-3">Type</th>
                <th className="px-6 py-3">Size</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr
                  key={d.id}
                  className="border-b border-white/5 hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3 text-sm">{d.original_filename}</td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {d.document_type.replace("_", " ")}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {formatSize(d.file_size)}
                  </td>
                  <td className="px-6 py-3">
                    <span className="text-xs px-2 py-1 rounded-full bg-cyan-500/20 text-cyan-400">
                      {d.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {new Date(d.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {documents.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-[#666]">
                    No documents uploaded
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex justify-center gap-4 mt-6">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="border border-white/20 px-4 py-2 rounded-lg disabled:opacity-30 hover:bg-white/5"
            >
              Previous
            </button>
            <span className="py-2 text-sm text-[#999]">
              Page {page} of {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="border border-white/20 px-4 py-2 rounded-lg disabled:opacity-30 hover:bg-white/5"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
