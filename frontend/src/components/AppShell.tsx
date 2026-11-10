"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { isPublicRoute } from "@/lib/public-routes";

interface NavLink {
  href: string;
  label: string;
}

interface NavGroup {
  label: string;
  links: NavLink[];
  roles?: string[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "OVERVIEW",
    links: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/chatbot", label: "Admission Chatbot" },
    ],
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
    links: [{ href: "/attendance", label: "Attendance" }],
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

function AuthGate() {
  const { signInWithGoogle, signInAsDev, authPhase, authError, clearAuthError } = useAuth();
  const isBusy = authPhase === "popup" || authPhase === "exchanging" || authPhase === "initializing";

  const handleSignIn = async () => {
    clearAuthError();
    await signInWithGoogle();
  };

  if (authPhase === "error" || authError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
        <div className="glass p-8 max-w-sm w-full mx-4 text-center rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
          <div className="eg-auth-icon-wrap eg-auth-icon-wrap--error mx-auto mb-4">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--danger, #EF4444)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          </div>
          <h2 className="eg-section__title text-lg mb-2 text-[var(--text-primary)]">Authentication Failed</h2>
          <p className="text-sm text-[var(--text-secondary)] mb-6 leading-relaxed">
            {authError || "Unable to complete sign-in. Please try again."}
          </p>
          <button onClick={handleSignIn} disabled={isBusy} className="eg-btn eg-btn-primary w-full">
            Try Again
          </button>
          <p className="mt-4">
            <Link href="/" className="text-xs text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors">
              &larr; Back to Home
            </Link>
          </p>
        </div>
      </div>
    );
  }

  if (authPhase === "popup" || authPhase === "exchanging") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
        <div className="glass p-10 max-w-sm w-full mx-4 text-center rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
          <div className="eg-auth-spinner mx-auto mb-5" />
          <p className="text-sm text-[var(--text-primary)] font-medium mb-1">
            {authPhase === "popup" ? "Waiting for Google sign-in..." : "Connecting to ExamGuard..."}
          </p>
          <p className="text-xs text-[var(--text-muted)]">
            Complete authentication in the popup window.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
      <div className="glass p-10 max-w-md w-full mx-4 text-center rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] shadow-2xl">
        <div className="eg-auth-icon-wrap mx-auto mb-5 bg-[var(--accent-soft)]">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect x="4" y="4" width="24" height="24" rx="6" stroke="var(--accent)" strokeWidth="1.5" opacity="0.4" />
            <circle cx="16" cy="13" r="4" stroke="var(--accent)" strokeWidth="1.5" />
            <path d="M9 25c0-3.87 3.13-7 7-7s7 3.13 7 7" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
        <h2 className="eg-section__title text-xl mb-1 text-[var(--text-primary)]">ExamGuard</h2>
        <p className="eg-eyebrow mb-4 text-[var(--accent-gold)]">Authentication Required</p>
        <p className="text-sm text-[var(--text-secondary)] mb-8 leading-relaxed">
          Sign in with your Google account to access the examination management system.
        </p>
        <button
          onClick={handleSignIn}
          disabled={isBusy}
          className="eg-btn eg-btn-primary w-full flex items-center justify-center gap-3 font-semibold"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
            <path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.997 8.997 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Continue with Google
        </button>

        {(process.env.NODE_ENV === "development" ||
          process.env.NEXT_PUBLIC_ENABLE_DEV_AUTH === "true") && (
          <div className="mt-5 pt-4 border-t border-[var(--border)]">
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-2.5 font-mono">Local Development Access</p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => signInAsDev?.("ADMIN")}
                disabled={isBusy}
                className="flex-1 py-2 px-3 text-xs font-medium rounded-lg bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] border border-[var(--border)] hover:border-[var(--accent-gold)] text-[var(--text-primary)] transition-colors"
              >
                Sign In as Admin
              </button>
              <button
                type="button"
                onClick={() => signInAsDev?.("REVIEWER")}
                disabled={isBusy}
                className="flex-1 py-2 px-3 text-xs font-medium rounded-lg bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] border border-[var(--border)] hover:border-[var(--accent-gold)] text-[var(--text-primary)] transition-colors"
              >
                Sign In as Invigilator
              </button>
            </div>
          </div>
        )}

        <p className="mt-6">
          <Link href="/" className="text-xs text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors">
            &larr; Back to Home
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, signOut, isAuthenticated: authed, loading } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [examAssignment, setExamAssignment] = useState<{
    account_role: string;
    exam_role: string | null;
    hall_name: string | null;
    assignment_status: string | null;
  } | null>(null);

  useEffect(() => {
    if (!authed) {
      return;
    }
    let cancelled = false;
    apiRequest<{
      account_role: string;
      exam_role: string | null;
      hall_name: string | null;
      assignment_status: string | null;
    }>("/api/v1/invigilator/my-assignment")
      .then((row) => {
        if (!cancelled) setExamAssignment(row);
      })
      .catch(() => {
        if (!cancelled) setExamAssignment(null);
      });
    return () => {
      cancelled = true;
    };
  }, [authed, pathname]);

  const visibleGroups = NAV_GROUPS.filter(group => {
    if (!group.roles) return true;
    if (!user) return false;
    return group.roles.includes(user.role);
  }).map(group => ({
    ...group,
    links: group.links.filter(link => {
      if (link.href !== "/invigilator") return true;
      if (!user) return false;
      if (user.role === "ADMIN" || user.role === "OPERATOR" || examAssignment?.exam_role === "INVIGILATOR") {
        return true;
      }
      const status = examAssignment?.assignment_status;
      return status === "SCHEDULED" || status === "ACTIVE";
    }),
  }));

  const publicRoute = isPublicRoute(pathname);

  if (!publicRoute) {
    if (!loading && !authed) {
      return <AuthGate />;
    }

    if (loading) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
          <div className="text-center">
            <div className="eg-auth-spinner mx-auto mb-4" />
            <p className="text-sm text-[var(--text-muted)]">Loading ExamGuard...</p>
          </div>
        </div>
      );
    }
  }

  // Determine active section for precision top header breadcrumb
  let activeTitle = "Operational Console";
  let activeGroupLabel = "OPERATIONS";
  for (const group of NAV_GROUPS) {
    for (const link of group.links) {
      if (isActive(pathname, link.href)) {
        activeTitle = link.label;
        activeGroupLabel = group.label;
        break;
      }
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] flex">
      {/* ── Persistent Desktop Sidebar ── */}
      <aside className="hidden lg:flex w-64 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex-col justify-between fixed top-0 bottom-0 left-0 z-30 select-none">
        <div className="flex flex-col min-h-0 flex-1">
          {/* Acid Liquid Chrome Brand Header */}
          <div className="h-16 flex items-center justify-between px-4 border-b border-[var(--border)] bg-black">
            <Link href="/" className="flex items-center gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/icon.svg" alt="ExamGuard" className="w-6 h-6 hover:rotate-12 transition-transform duration-300" />
              <span className="font-extrabold text-sm tracking-tight text-white acid-chromatic uppercase font-[family-name:var(--font-syne)]">
                EXAMGUARD
              </span>
            </Link>
            <span className="text-[9px] font-mono px-2 py-0.5 rounded border border-[#CCFF00] text-[#CCFF00] bg-[#CCFF00]/10 tracking-widest font-black shadow-[0_0_12px_rgba(204,255,0,0.3)]">
              ACID V3
            </span>
          </div>

          {/* Navigation Groups */}
          <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5" aria-label="Sidebar Navigation">
            {visibleGroups.map((group) => (
              <div key={group.label} className="space-y-1">
                <p className="px-2.5 text-[10px] font-mono font-bold tracking-widest text-[#8E93A4] uppercase">
                  {group.label}
                </p>
                <div className="space-y-0.5 pt-0.5">
                  {group.links.map((link) => {
                    const active = isActive(pathname, link.href);
                    return (
                      <Link
                        key={link.href}
                        href={link.href}
                        className={`group flex items-center justify-between px-3 py-1.5 rounded text-xs transition-all ${
                          active
                            ? "bg-[#CCFF00]/10 text-white border-l-2 border-[#CCFF00] font-bold pl-2.5 shadow-[0_0_18px_rgba(204,255,0,0.25)]"
                            : "text-[var(--text-muted)] hover:text-white hover:bg-[var(--bg-surface)] hover:border-l border-white/20"
                        }`}
                      >
                        <span className={active ? "text-[#CCFF00]" : ""}>{link.label}</span>
                        {active && (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#CCFF00] shadow-[0_0_8px_#CCFF00]" />
                        )}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>

        {/* Operational Status Footer in Sidebar */}
        <div className="p-3.5 border-t border-[var(--border)] bg-[#07070A]">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#8E93A4]">TELEMETRY HUD</span>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#CCFF00] shadow-[0_0_10px_#CCFF00] animate-pulse" />
              <span className="text-[10px] font-mono text-[#CCFF00] font-black tracking-wider">VOLT ONLINE</span>
            </div>
          </div>
          <div className="flex items-center justify-between text-[10px] font-mono text-[#8E93A4] border-t border-[var(--border-subtle)] pt-1.5">
            <span>LATENCY: 18ms</span>
            <span className="text-[#00F0FF] font-semibold">ONNX ACID</span>
          </div>
        </div>
      </aside>

      {/* ── Main Application Column ── */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64">
        {/* ── Unified Sticky Header Suite (Ticker + Navigation Bar) ── */}
        <div className="sticky top-0 z-20 shrink-0">
          {/* Continuous Acid Marquee Ticker */}
          <div className="bg-black/95 border-b border-[#CCFF00]/20 overflow-hidden h-6 select-none flex items-center">
            <div className="relative flex overflow-x-hidden w-full items-center">
              <div className="animate-acid-marquee flex items-center gap-8 text-[10px] font-mono font-bold tracking-widest text-[#CCFF00] shrink-0">
                <span>⚡ EXAMGUARD PROTOCOL // LIQUID CHROME CORE // ONNX AI BIOMETRIC INFERENCE</span>
                <span className="text-[#FF00FF]">✦ ZERO-TRUST ADMISSION GATE ✦</span>
                <span className="text-[#00F0FF]">⬡ HIGH-FREQUENCY IDENTITY VERIFICATION ACTIVE</span>
                <span className="text-[#E0E2EC]">⚡ CRYPTOGRAPHIC ATTENDANCE LEDGER VERIFIED</span>
              </div>
              <div className="animate-acid-marquee flex items-center gap-8 text-[10px] font-mono font-bold tracking-widest text-[#CCFF00] shrink-0" aria-hidden="true">
                <span>⚡ EXAMGUARD PROTOCOL // LIQUID CHROME CORE // ONNX AI BIOMETRIC INFERENCE</span>
                <span className="text-[#FF00FF]">✦ ZERO-TRUST ADMISSION GATE ✦</span>
                <span className="text-[#00F0FF]">⬡ HIGH-FREQUENCY IDENTITY VERIFICATION ACTIVE</span>
                <span className="text-[#E0E2EC]">⚡ CRYPTOGRAPHIC ATTENDANCE LEDGER VERIFIED</span>
              </div>
            </div>
          </div>

          {/* ── Persistent Top Header ── */}
          <header className="h-14 bg-[var(--bg-secondary)]/95 backdrop-blur-md border-b border-[var(--border)] px-4 lg:px-8 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Mobile Hamburger */}
              <button
                type="button"
                className="lg:hidden p-2 rounded-md hover:bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                onClick={() => setMobileOpen(!mobileOpen)}
                aria-label="Toggle navigation menu"
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>

              {/* Breadcrumb Info */}
              <div className="flex items-center gap-2 text-xs">
                <span className="text-[11px] font-mono tracking-wider text-[var(--text-muted)] uppercase hidden sm:inline">
                  {activeGroupLabel}
                </span>
                <span className="text-[var(--border)] hidden sm:inline">/</span>
                <span className="font-semibold text-sm text-[var(--text-primary)] tracking-tight">{activeTitle}</span>
              </div>
            </div>

            {/* Right Header: Role & User Status */}
            <div className="flex items-center gap-3">
              {authed && user && (
                <div className="hidden sm:flex items-center gap-2.5 px-3 py-1.5 rounded-md bg-[var(--bg-surface)] border border-[var(--border)]">
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#CCFF00] shadow-[0_0_8px_#CCFF00]" />
                    <span className="text-[11px] font-mono font-bold text-[#CCFF00] uppercase tracking-wider">
                      {examAssignment?.account_role || user.role}
                    </span>
                  </div>
                  {examAssignment?.hall_name && (
                    <span className="text-xs text-[var(--text-secondary)] border-l border-[var(--border)] pl-2">
                      {examAssignment.hall_name}
                    </span>
                  )}
                  {user.full_name && (
                    <span className="text-xs text-[var(--text-secondary)] border-l border-[var(--border)] pl-2 max-w-[140px] truncate">
                      {user.full_name}
                    </span>
                  )}
                </div>
              )}

              {authed ? (
                <button
                  type="button"
                  onClick={() => signOut()}
                  className="px-3.5 py-1.5 text-xs font-mono uppercase tracking-wider rounded-md bg-[var(--bg-surface)] hover:bg-[var(--bg-surface-elevated)] border border-[var(--border)] hover:border-[#CCFF00] hover:text-[#CCFF00] transition-colors"
                >
                  Sign Out
                </button>
              ) : (
                <Link
                  href="/"
                  className="px-4 py-1.5 text-xs font-bold uppercase tracking-tight rounded-md btn-chrome text-black transition-all"
                >
                  ⚡ Sign In
                </Link>
              )}
            </div>
          </header>
        </div>

        {/* ── Mobile Navigation Drawer ── */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div
              className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity"
              onClick={() => setMobileOpen(false)}
            />
            <div className="fixed inset-y-0 left-0 w-72 bg-[var(--bg-secondary)] border-r border-[var(--border)] p-5 flex flex-col justify-between overflow-y-auto z-50 shadow-2xl">
              <div>
                <div className="flex items-center justify-between pb-4 mb-4 border-b border-[var(--border)]">
                  <Link href="/" onClick={() => setMobileOpen(false)} className="flex items-center gap-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src="/icon.svg" alt="ExamGuard" className="w-6 h-6" />
                    <span className="font-semibold text-sm text-[var(--text-primary)]">ExamGuard</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => setMobileOpen(false)}
                    className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    aria-label="Close navigation"
                  >
                    ✕
                  </button>
                </div>
                <div className="space-y-4">
                  {visibleGroups.map((group) => (
                    <div key={group.label} className="space-y-1">
                      <p className="text-[10px] font-mono font-bold tracking-widest text-[var(--text-muted)] uppercase px-2">
                        {group.label}
                      </p>
                      <div className="space-y-0.5">
                        {group.links.map((link) => (
                          <Link
                            key={link.href}
                            href={link.href}
                            onClick={() => setMobileOpen(false)}
                            className={`block px-3 py-2 text-xs rounded font-medium transition-colors ${
                              isActive(pathname, link.href)
                                ? "bg-[var(--bg-surface)] text-[var(--text-primary)] border-l-2 border-[var(--accent-gold)] pl-2.5"
                                : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
                            }`}
                          >
                            {link.label}
                          </Link>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-[var(--border)] mt-6">
                {authed && user ? (
                  <div className="space-y-2">
                    <p className="text-xs text-[var(--text-secondary)] truncate">{user.full_name || user.email}</p>
                    <button
                      type="button"
                      onClick={() => {
                        signOut();
                        setMobileOpen(false);
                      }}
                      className="w-full py-2 text-xs rounded bg-[var(--bg-surface)] border border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    >
                      Sign Out
                    </button>
                  </div>
                ) : (
                  <Link
                    href="/"
                    onClick={() => setMobileOpen(false)}
                    className="block text-center w-full py-2 text-xs font-semibold rounded bg-[var(--accent-gold)] text-[#08080D]"
                  >
                    Sign In
                  </Link>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Main Page Content ── */}
        <main className="flex-1 min-w-0">{children}</main>
      </div>
    </div>
  );
}
