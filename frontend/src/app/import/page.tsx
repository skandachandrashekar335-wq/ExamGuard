import Link from "next/link";
import AppShell from "@/components/AppShell";

const IMPORT_TYPES = [
  {
    title: "Students",
    href: "/import/students",
    description: "Bulk import student records from Excel or CSV",
    limit: "Max 500 per batch",
    icon: "🎓",
  },
  {
    title: "Subjects & Exams",
    href: "/import/subjects-exams",
    description: "Import subjects and examination schedules",
    limit: "Subjects: 200, Exams: 500",
    icon: "📚",
  },
  {
    title: "Registrations",
    href: "/import/registrations",
    description: "Bulk register students for exams",
    limit: "Max 500 per batch",
    icon: "📝",
  },
  {
    title: "Seat Assignments",
    href: "/import/seat-assignments",
    description: "Bulk assign seats in exam halls",
    limit: "Max 200 per batch",
    icon: "💺",
  },
];

export default function ImportHubPage() {
  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <h1 className="eg-page-title">Data Import</h1>
          <p className="eg-page-desc">Upload Excel or CSV files to bulk import data</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {IMPORT_TYPES.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="glass-surface glass-medium p-6 hover:border-[var(--accent)]/30 transition-all group block"
            >
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl">{item.icon}</span>
                <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                  {item.title}
                </h2>
              </div>
              <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>
                {item.description}
              </p>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>{item.limit}</p>
            </Link>
          ))}
        </div>

        <div className="mt-8 flex gap-4">
          <Link href="/import/history" className="eg-btn eg-btn-secondary">
            View Import History
          </Link>
          <Link href="/" className="eg-btn text-sm" style={{ color: "var(--text-muted)" }}>
            &larr; Back to Home
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
