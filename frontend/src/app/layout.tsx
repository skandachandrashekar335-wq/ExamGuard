import type { Metadata } from "next";
import { Playfair_Display, Source_Serif_4, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import * as React from "react";
import { AuthProvider } from "@/context/AuthContext";
import { isAuthenticated, getUserDisplayName } from "@/lib/firebase";
import type { ReactNode } from "react";

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["300", "400", "500"],
});

export const metadata: Metadata = {
  title: "ExamGuard — Automated Examination Entry Verification",
  description:
    "AI-powered examination entry verification system connecting hall-ticket context with identity verification before entry is authorized.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${playfair.variable} ${sourceSerif.variable} ${jetbrainsMono.variable} h-full`}
    >
      <body className="min-h-full flex flex-col bg-[var(--bg-light)] text-[var(--text-primary)]">
        <AuthProvider>
          {/* Sticky Navigation */}
          <header className="sticky-nav bg-[var(--bg-raised)] border-b border-[var(--border)]">
            <div className="max-w-7xl mx-auto px-6 sm:px-10 height-full flex items-center justify-between">
              <div className="flex items-center gap-2">
                <a href="/" className="eg-mono-sm font-medium uppercase tracking-wider text-[var(--black)]">
                  EXAMGUARD
                </a>
                <nav className="hidden sm:block sm:flex items-center gap-8">
                  <a href="/examination-sessions" className="eg-mono-sm text-[var(--gray-55)] hover:text-[var(--black)] transition-colors duration-200">
                    PRODUCT
                  </a>
                  <a href="/identity-verifications" className="eg-mono-sm text-[var(--gray-55)] hover:text-[var(--black)] transition-colors duration-200">
                    VERIFICATION
                  </a>
                  <a href="/exams" className="eg-mono-sm text-[var(--gray-55)] hover:text-[var(--black)] transition-colors duration-200">
                    SECURITY
                  </a>
                  <a href="/monitoring" className="eg-mono-sm text-[var(--gray-55)] hover:text-[var(--black)] transition-colors duration-200">
                    ANALYTICS
                  </a>
                  <a href="/security-events" className="eg-mono-sm text-[var(--gray-55)] hover:text-[var(--black)] transition-colors duration-200">
                    AUDIT
                  </a>
                </nav>
                <a href="/examination-sessions" className="eg-btn eg-btn-sm eg-btn-primary uppercase rounded-md px-3 text-xs">
                  ACCESS SYSTEM
                </a>
              </div>

              {/* Authenticated user menu */}
              {isAuthenticated() ? (
                <div className="flex items-center gap-2">
                  <span className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider">
                    {getUserDisplayName()}
                  </span>
                  <button
                    onClick={() => {
                      // Sign out handling - will be handled by AuthContext
                      window.dispatchEvent(
                        new Event("auth-sign-out", { bubbles: true })
                      );
                    }}
                    className="eg-btn eg-btn-sm eg-btn-primary uppercase rounded-md px-3 text-xs"
                  >
                    LOG OUT
                  </button>
                </div>
              ) : (
                <a href="/examination-sessions" className="eg-btn eg-btn-sm eg-btn-primary uppercase rounded-md px-3 text-xs">
                  ACCESS SYSTEM
                </a>
              )}
            </div>
          </header>

          {/* Main content */}
          <main className="flex-1 p-6">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}