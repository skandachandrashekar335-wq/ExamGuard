import Link from "next/link";

const IMPORT_TYPES = [
  {
    title: "Students",
    href: "/import/students",
    description: "Bulk import student records from a JSON file",
    limit: "Max 500 per batch",
    color: "from-cyan-500 to-blue-500",
  },
  {
    title: "Subjects & Exams",
    href: "/import/subjects-exams",
    description: "Import subjects and examination schedules",
    limit: "Subjects: 200, Exams: 500",
    color: "from-emerald-500 to-cyan-500",
  },
  {
    title: "Registrations",
    href: "/import/registrations",
    description: "Bulk register students for exams",
    limit: "Max 500 per batch",
    color: "from-pink-500 to-purple-500",
  },
  {
    title: "Seat Assignments",
    href: "/import/seat-assignments",
    description: "Bulk assign seats in exam halls",
    limit: "Max 200 per batch",
    color: "from-amber-500 to-pink-500",
  },
];

export default function ImportHubPage() {
  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Data Import
        </h1>
        <p className="text-[#999] mb-8">
          Bulk import data into the system
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {IMPORT_TYPES.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block bg-[#111] border border-white/10 rounded-lg p-6 hover:border-white/20 transition-colors group"
            >
              <h2
                className={`text-xl font-semibold mb-2 bg-gradient-to-r ${item.color} bg-clip-text text-transparent`}
              >
                {item.title}
              </h2>
              <p className="text-[#999] text-sm mb-4">{item.description}</p>
              <p className="text-[#666] text-xs">{item.limit}</p>
            </Link>
          ))}
        </div>

        <div className="mt-8">
          <Link
            href="/"
            className="text-[#666] hover:text-white text-sm transition-colors"
          >
            &larr; Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
