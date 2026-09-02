import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center">
      <main className="text-center">
        <h1 className="text-5xl font-bold uppercase tracking-wider mb-4">
          ExamGuard
        </h1>
        <p className="text-[#999] text-lg mb-8">
          AI-powered Examination Entry Verification Platform
        </p>
        <div className="flex gap-4">
          <Link
            href="/dashboard"
            className="inline-block bg-gradient-to-r from-cyan-500 to-emerald-500 px-8 py-3 rounded-lg font-medium hover:opacity-90 transition-opacity"
          >
            Verification Dashboard
          </Link>
          <Link
            href="/students"
            className="inline-block border border-white/20 px-8 py-3 rounded-lg font-medium hover:bg-white/5 transition-colors"
          >
            Manage Students
          </Link>
          <Link
            href="/documents"
            className="inline-block border border-white/20 px-8 py-3 rounded-lg font-medium hover:bg-white/5 transition-colors"
          >
            Upload Documents
          </Link>
        </div>
      </main>
    </div>
  );
}
