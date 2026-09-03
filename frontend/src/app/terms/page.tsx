import Link from "next/link";

export const metadata = {
  title: "Terms & Conditions — ExamGuard",
  description: "ExamGuard terms and conditions covering system usage, examination verification, and responsibilities.",
};

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
        <Link href="/" className="eg-focusable inline-block eg-label mb-8 hover:text-[var(--text-secondary)] transition-colors">
          ← BACK TO EXAMGUARD
        </Link>

        <h1 className="text-3xl sm:text-4xl font-bold uppercase tracking-wider mb-2">
          Terms & Conditions
        </h1>
        <p className="eg-label mb-12">EXAMGUARD — EXAMINATION ENTRY VERIFICATION SYSTEM</p>

        <div className="space-y-12">
          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">1. System Description</h2>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              ExamGuard is an automated examination entry verification system.
              It connects hall-ticket document verification with identity
              verification to support examination entry authorization decisions.
              The system is designed to assist examination administrators, not
              to replace human judgment.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">2. Verification Purpose</h2>
            <p className="text-[var(--text-secondary)] leading-relaxed mb-4">
              The system performs two distinct verification processes:
            </p>
            <div className="space-y-3">
              <div className="eg-card">
                <h3 className="text-sm font-bold uppercase tracking-wider mb-2 text-[var(--accent-cyan)]">
                  Hall-Ticket Verification
                </h3>
                <p className="text-[var(--text-secondary)] text-sm leading-relaxed">
                  Validates uploaded hall-ticket documents through OCR text
                  extraction and matching against student and examination records.
                </p>
              </div>
              <div className="eg-card">
                <h3 className="text-sm font-bold uppercase tracking-wider mb-2 text-[var(--accent-emerald)]">
                  Identity Verification
                </h3>
                <p className="text-[var(--text-secondary)] text-sm leading-relaxed">
                  Verifies that the person presenting the hall ticket matches
                  the registered student. Currently supports manual and
                  document-based methods. Face verification is planned
                  for a future phase.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">3. Verification ≠ Authorization</h2>
            <div className="eg-card border-[var(--accent-amber)]/30">
              <p className="text-[var(--text-secondary)] text-sm leading-relaxed">
                <strong className="text-[var(--accent-amber)]">Important:</strong> ExamGuard provides
                verification evidence and supports decision-making. It does not
                automatically authorize or deny examination entry. All entry
                authorization decisions are made by authorized examination
                administrators based on the evidence provided by the system.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">4. System Limitations</h2>
            <ul className="text-[var(--text-secondary)] leading-relaxed list-disc list-inside space-y-2">
              <li>OCR extraction may not be 100% accurate for all document formats</li>
              <li>Document matching is based on available data and may produce inconclusive results</li>
              <li>Identity verification accuracy depends on the verification method and data quality</li>
              <li>The system does not guarantee detection of all cases of identity fraud</li>
              <li>System availability depends on infrastructure and configuration</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">5. Administrator Responsibilities</h2>
            <ul className="text-[var(--text-secondary)] leading-relaxed list-disc list-inside space-y-2">
              <li>Ensure student and examination data is accurately imported</li>
              <li>Review verification results before making entry authorization decisions</li>
              <li>Handle verification failures and inconclusive results appropriately</li>
              <li>Maintain system configuration and access controls</li>
              <li>Ensure compliance with institutional policies and applicable regulations</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">6. Data Accuracy</h2>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              The accuracy of verification results depends on the accuracy of
              the underlying data. Administrators are responsible for ensuring
              that student records, examination data, and hall ticket
              information are correct and up to date.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">7. No Guarantees</h2>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              ExamGuard is provided as a tool to assist examination
              administration. No specific guarantees are made regarding
              system accuracy, availability, or fitness for any particular
              purpose. The system is used at the discretion of the
              examination administration.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">8. System Evolution</h2>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              ExamGuard is under active development. Features described
              in the project roadmap are planned but not guaranteed.
              Current functionality is limited to what is documented
              in the system documentation. Future phases may introduce
              new capabilities including face verification, real-time
              monitoring, and additional security features.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">9. Changes to Terms</h2>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              These terms may be updated as the system evolves and its
              capabilities change. Significant changes to system
              functionality or verification processes will be documented.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-4">10. Acceptance</h2>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              By using the ExamGuard system, administrators acknowledge
              these terms and the system&apos;s capabilities and limitations
              as described in this document and the system documentation.
            </p>
          </section>
        </div>

        <div className="mt-16 pt-8 border-t border-[var(--border)]">
          <Link href="/" className="eg-focusable text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors">
            ← Back to ExamGuard
          </Link>
        </div>
      </div>
    </div>
  );
}
