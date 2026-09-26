"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";

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
  const { signInWithGoogle, authPhase, authError, clearAuthError } = useAuth();
  const isBusy = authPhase === "popup" || authPhase === "exchanging" || authPhase === "initializing";

  const handleSignIn = async () => {
    clearAuthError();
    await signInWithGoogle();
  };

  if (authPhase === "error" || authError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
        <div className="glass p-8 max-w-sm w-full mx-4 text-center">
          <div className="eg-auth-icon-wrap eg-auth-icon-wrap--error mx-auto mb-4">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--danger, #dc3545)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          </div>
          <h2 className="eg-section__title text-lg mb-2">Authentication Failed</h2>
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
        <div className="glass p-10 max-w-sm w-full mx-4 text-center">
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
      <div className="glass p-10 max-w-md w-full mx-4 text-center">
        <div className="eg-auth-icon-wrap mx-auto mb-5">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect x="4" y="4" width="24" height="24" rx="6" stroke="var(--accent)" strokeWidth="1.5" opacity="0.4" />
            <circle cx="16" cy="13" r="4" stroke="var(--accent)" strokeWidth="1.5" />
            <path d="M9 25c0-3.87 3.13-7 7-7s7 3.13 7 7" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
        <h2 className="eg-section__title text-xl mb-2">ExamGuard</h2>
        <p className="eg-eyebrow mb-4">Authentication Required</p>
        <p className="text-sm text-[var(--text-secondary)] mb-8 leading-relaxed">
          Sign in with your Google account to access the examination management system.
        </p>
        <button
          onClick={handleSignIn}
          disabled={isBusy}
          className="eg-btn eg-btn-primary w-full flex items-center justify-center gap-3"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
            <path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.997 8.997 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Continue with Google
        </button>
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
  const router = useRouter();
  const { user, signOut, isAuthenticated: authed, loading } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [justSignedIn, setJustSignedIn] = useState(false);

  useEffect(() => {
    if (justSignedIn && authed && !loading) {
      setJustSignedIn(false);
      router.push("/dashboard");
    }
  }, [justSignedIn, authed, loading, router]);

  const visibleGroups = NAV_GROUPS.filter(group => {
    if (!group.roles) return true;
    if (!user) return false;
    return group.roles.includes(user.role);
  });

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

  return (
    <div className="min-h-screen">
      <header className="eg-app-nav">
        <div className="eg-app-nav-inner">
          <div className="eg-app-nav-left">
            <Link href="/" className="eg-app-nav-brand">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/icon.svg" alt="ExamGuard" className="w-6 h-6" />
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
