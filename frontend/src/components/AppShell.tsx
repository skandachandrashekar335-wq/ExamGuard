"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/examination-sessions", label: "Sessions" },
  { href: "/identity-verifications", label: "Verification" },
  { href: "/attendance", label: "Attendance" },
  { href: "/monitoring", label: "Monitoring" },
  { href: "/security-events", label: "Security" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, signOut, isAuthenticated: authed } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="min-h-screen">
      <header className="eg-app-nav">
        <div className="eg-app-nav-inner">
          <div className="eg-app-nav-left">
            <Link href="/" className="eg-app-nav-brand">
              <span className="w-6 h-6 rounded-[6px] bg-[var(--accent)] flex items-center justify-center text-white text-xs font-bold" style={{ fontFamily: "var(--font-display)" }}>E</span>
              ExamGuard
            </Link>
            <nav className="eg-app-nav-links eg-hide-mobile">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`eg-app-nav-link ${isActive(link.href) ? "eg-app-nav-link-active" : ""}`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="eg-app-nav-right">
            {authed && user && (
              <span className="eg-mono-sm text-[var(--text-muted)] eg-hide-mobile hidden md:block">
                {user.role}
              </span>
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
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMobileOpen(false)}
              className={isActive(link.href) ? "text-[var(--accent)]" : ""}
            >
              {link.label}
            </Link>
          ))}
        </div>
      )}

      <main>{children}</main>
    </div>
  );
}
