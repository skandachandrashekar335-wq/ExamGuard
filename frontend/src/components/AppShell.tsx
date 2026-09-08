"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";

interface NavLink {
  href: string;
  label: string;
  icon?: string;
}

interface NavGroup {
  label: string;
  links: NavLink[];
  roles?: string[]; // If set, only these roles see this group
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "OVERVIEW",
    links: [{ href: "/dashboard", label: "Dashboard" }],
  },
  {
    label: "EXAM SETUP",
    links: [
      { href: "/exams", label: "Examinations" },
      { href: "/exam-prep", label: "Prepare Exam" },
      { href: "/students", label: "Students" },
      { href: "/hall-tickets", label: "Hall Tickets" },
      { href: "/exam-halls", label: "Halls" },
      { href: "/entry-points", label: "Entry Points" },
      { href: "/cameras", label: "Cameras" },
    ],
    roles: ["ADMIN", "OPERATOR"],
  },
  {
    label: "EXAM DAY",
    links: [
      { href: "/invigilator", label: "Invigilator" },
      { href: "/examination-sessions", label: "Sessions" },
      { href: "/verify", label: "Verify Entry" },
      { href: "/monitoring", label: "Monitoring" },
    ],
  },
  {
    label: "ATTENDANCE",
    links: [
      { href: "/attendance", label: "Attendance" },
    ],
  },
  {
    label: "SECURITY",
    links: [
      { href: "/security-events", label: "Events" },
      { href: "/security-alerts", label: "Alerts" },
    ],
  },
  {
    label: "DATA",
    links: [
      { href: "/documents", label: "Documents" },
      { href: "/import", label: "Import" },
      { href: "/audit", label: "Audit" },
    ],
    roles: ["ADMIN", "OPERATOR"],
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(href + "/");
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, signOut, isAuthenticated: authed, loading, signInWithGoogle } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Filter nav groups by user role
  const visibleGroups = NAV_GROUPS.filter(group => {
    if (!group.roles) return true;
    if (!user) return false;
    return group.roles.includes(user.role);
  });

  // Auth guard: show login prompt if not authenticated
  if (!loading && !authed) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="glass p-8 max-w-md w-full text-center">
          <h2 className="eg-section__title text-xl mb-4">Sign In Required</h2>
          <p className="text-[var(--text-secondary)] mb-6">
            You must sign in to access ExamGuard.
          </p>
          <button
            onClick={() => signInWithGoogle()}
            className="eg-btn eg-btn-primary"
          >
            Continue with Google
          </button>
          <p className="mt-4">
            <Link href="/" className="text-sm text-[var(--accent)]">← Back to Home</Link>
          </p>
        </div>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-[var(--text-muted)]">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="eg-app-nav">
        <div className="eg-app-nav-inner">
          <div className="eg-app-nav-left">
            <Link href="/" className="eg-app-nav-brand">
              <span className="w-6 h-6 rounded-[6px] bg-[var(--accent)] flex items-center justify-center text-white text-xs font-bold" style={{ fontFamily: "var(--font-display)" }}>E</span>
              <span className="hidden sm:inline">ExamGuard</span>
            </Link>
            <nav className="eg-app-nav-links eg-hide-mobile">
              {visibleGroups.map((group) => (
                <div key={group.label} className="eg-nav-group">
                  {group.links.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`eg-app-nav-link ${isActive(pathname, link.href) ? "eg-app-nav-link-active" : ""}`}
                    >
                      {link.label}
                    </Link>
                  ))}
                </div>
              ))}
            </nav>
          </div>
          <div className="eg-app-nav-right">
            {authed && user && (
              <div className="flex items-center gap-2">
                <span className="eg-mono-sm text-[var(--text-muted)] eg-hide-mobile hidden md:block">
                  {user.role}
                </span>
                {user.full_name && (
                  <span className="text-xs text-[var(--text-secondary)] eg-hide-mobile hidden md:block max-w-[120px] truncate">
                    {user.full_name}
                  </span>
                )}
              </div>
            )}
            {authed ? (
              <button
                onClick={() => signOut()}
                className="eg-btn eg-btn-sm text-xs px-3 py-1.5"
              >
                Sign Out
              </button>
            ) : (
              <Link href="/" className="eg-btn eg-btn-primary eg-btn-sm text-xs px-3 py-1.5">
                Sign In
              </Link>
            )}
            <button
              className="eg-mobile-menu-btn"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Menu"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {mobileOpen && (
        <div className="eg-mobile-menu">
          <button className="eg-mobile-menu-close" onClick={() => setMobileOpen(false)}>✕</button>
          {visibleGroups.map((group) => (
            <div key={group.label} className="eg-mobile-nav-group">
              <p className="eg-mobile-nav-label">{group.label}</p>
              {group.links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={isActive(pathname, link.href) ? "text-[var(--accent)]" : ""}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          ))}
        </div>
      )}

      <main>{children}</main>
    </div>
  );
}
