import Link from "next/link";

export const metadata = {
  title: "Privacy Policy — ExamGuard",
  description: "ExamGuard privacy policy covering data handling, identity verification, and biometric processing.",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)]">
      <div className="max-w-3xl mx-auto px-6 sm:px-10 py-16 sm:py-24">
        <Link href="/" className="eg-focusable inline-block eg-mono-sm mb-8 hover:text-[var(--text-secondary)] transition-colors">
          ← BACK TO EXAMGUARD
        </Link>

        <h1 className="eg-display text-3xl sm:text-4xl mb-2">
          Privacy Policy
        </h1>
        <p className="eg-mono-sm text-[var(--gray-500)] mb-12">EXAMGUARD — EXAMINATION ENTRY VERIFICATION SYSTEM</p>

        <div className="space-y-12">
          <section>
            <h2 className="eg-display text-xl mb-4">1. Overview</h2>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed mb-4">
              ExamGuard is an automated examination entry verification system.
              This privacy policy describes how the system handles data related
              to students, examination registrations, hall tickets, and identity
              verification attempts.
            </p>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
              This policy applies to the ExamGuard system operated as described
              in the project documentation. It covers data collection, processing,
              storage, and the specific handling of identity verification data.
            </p>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">2. Data Collected</h2>
            <div className="space-y-4">
              <div className="eg-card">
                <h3 className="eg-mono-sm text-[var(--gray-500)] mb-2">
                  Student Information
                </h3>
                <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
                  USN (University Seat Number), student name. These are stored
                  as part of the student management system and are required for
                  examination registration and verification.
                </p>
              </div>
              <div className="eg-card">
                <h3 className="eg-mono-sm text-[var(--gray-500)] mb-2">
                  Examination Data
                </h3>
                <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
                  Examination details (subject, date, time, semester, department),
                  exam hall assignments, seat assignments, and examination
                  registrations. This data is managed by the examination
                  administration.
                </p>
              </div>
              <div className="eg-card">
                <h3 className="eg-mono-sm text-[var(--gray-500)] mb-2">
                  Hall Ticket Documents
                </h3>
                <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
                  Uploaded hall ticket documents (PDF, images) processed through
                  OCR for text extraction. Document content is used for
                  verification matching against student and examination records.
                </p>
              </div>
              <div className="eg-card">
                <h3 className="eg-mono-sm text-[var(--gray-500)] mb-2">
                  Identity Verification Data
                </h3>
                <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
                  Identity verification attempts, verification method used,
                  verification decisions (MATCH, NO_MATCH, INCONCLUSIVE),
                  and verification status. <strong>Currently implemented:
                  manual and document-based verification methods only.</strong>
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">3. Biometric Data</h2>
            <div className="eg-card border-[var(--gray-600)]">
              <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed mb-3">
                <strong>Currently implemented:</strong> No biometric
                data is collected, stored, or processed. The system does not
                currently perform face recognition, fingerprint scanning, or any
                other biometric identification.
              </p>
              <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed mb-3">
                <strong>Planned for future:</strong> Phase 8 of the
                project plans to introduce face verification through a third-party
                provider. If implemented:
              </p>
              <ul className="eg-body text-sm text-[var(--gray-400)] leading-relaxed list-disc list-inside space-y-1">
                <li>Raw facial images are NOT stored by ExamGuard</li>
                <li>Biometric templates would be managed by the third-party provider</li>
                <li>ExamGuard would store only verification evidence signals (similarity scores, liveness results)</li>
                <li>No biometric data is shared with third parties beyond the verification provider</li>
              </ul>
            </div>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">4. Data Processing</h2>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed mb-4">
              Data is processed for the following purposes:
            </p>
            <ul className="eg-body text-sm text-[var(--gray-400)] leading-relaxed list-disc list-inside space-y-2">
              <li>Examination registration management</li>
              <li>Hall ticket verification through OCR and document matching</li>
              <li>Identity verification (manual and document-based, currently)</li>
              <li>Examination entry authorization decisions</li>
              <li>Audit logging of verification activities</li>
              <li>System administration and configuration</li>
            </ul>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">5. Data Storage</h2>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
              All data is stored in the system database. Document files are
              stored in the configured storage location. The system maintains
              audit trails for verification activities. No data is transmitted
              to external services beyond the configured verification provider
              (if any).
            </p>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">6. Data Retention</h2>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
              Data is retained as long as necessary for examination
              administration purposes. Audit logs are maintained for
              accountability. Specific retention periods are configured
              by the system administrator.
            </p>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">7. Access Controls</h2>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
              Access to student data, verification results, and system
              administration is controlled through role-based access
              controls (currently planned for Phase 19). System
              administrators have full access. Operator and reviewer
              roles are planned.
            </p>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">8. Third-Party Services</h2>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
              Currently, no third-party AI or cloud services are connected
              to the system. All processing is performed locally. Future
              integrations (such as face verification providers) will be
              documented and this policy will be updated accordingly.
            </p>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">9. Changes to This Policy</h2>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
              This privacy policy may be updated as the system evolves.
              Changes will be reflected in the project documentation and
              this page. Significant changes to data handling practices
              will be documented.
            </p>
          </section>

          <section>
            <h2 className="eg-display text-xl mb-4">10. Contact</h2>
            <p className="eg-body text-sm text-[var(--gray-400)] leading-relaxed">
              For questions about this privacy policy or the ExamGuard
              system&apos;s data handling practices, refer to the project
              documentation or contact the system administrator.
            </p>
          </section>
        </div>

        <div className="mt-16 pt-8 border-t border-[var(--border)]">
          <Link href="/" className="eg-focusable eg-mono-sm text-[var(--gray-500)] hover:text-[var(--text-secondary)] transition-colors">
            ← Back to ExamGuard
          </Link>
        </div>
      </div>
    </div>
  );
}
