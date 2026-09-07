import Link from "next/link";
import AppShell from "@/components/AppShell";

export const metadata = {
  title: "Terms & Conditions — ExamGuard",
  description: "ExamGuard terms and conditions covering system usage, examination verification, and responsibilities.",
};

export default function TermsPage() {
  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/" className="eg-breadcrumb">
            ← BACK TO EXAMGUARD
          </Link>
          <h1 className="eg-page-title">Terms & Conditions</h1>
          <p className="eg-page-desc">EXAMGUARD — EXAMINATION ENTRY VERIFICATION SYSTEM</p>
        </div>

        <div className="eg-content-sections">
          <section className="eg-content-section">
            <h2 className="eg-content-heading">1. System Description</h2>
            <p className="eg-body">
              ExamGuard is an automated examination entry verification system.
              It connects hall-ticket document verification with identity
              verification to support examination entry authorization decisions.
              The system is designed to assist examination administrators, not
              to replace human judgment.
            </p>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">2. Verification Purpose</h2>
            <p className="eg-body">
              The system performs two distinct verification processes:
            </p>
            <div className="eg-content-cards">
              <div className="glass-surface glass p-4">
                <h3 className="eg-content-subheading">Hall-Ticket Verification</h3>
                <p className="eg-body">
                  Validates uploaded hall-ticket documents through OCR text
                  extraction and matching against student and examination records.
                </p>
              </div>
              <div className="glass-surface glass p-4">
                <h3 className="eg-content-subheading">Identity Verification</h3>
                <p className="eg-body">
                  Verifies that the person presenting the hall ticket matches
                  the registered student. Currently supports manual and
                  document-based methods. Face verification is planned
                  for a future phase.
                </p>
              </div>
            </div>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">3. Verification ≠ Authorization</h2>
            <div className="glass-surface glass p-4">
              <p className="eg-body">
                <strong>Important:</strong> ExamGuard provides
                verification evidence and supports decision-making. It does not
                automatically authorize or deny examination entry. All entry
                authorization decisions are made by authorized examination
                administrators based on the evidence provided by the system.
              </p>
            </div>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">4. System Limitations</h2>
            <ul className="eg-body eg-content-list">
              <li>OCR extraction may not be 100% accurate for all document formats</li>
              <li>Document matching is based on available data and may produce inconclusive results</li>
              <li>Identity verification accuracy depends on the verification method and data quality</li>
              <li>The system does not guarantee detection of all cases of identity fraud</li>
              <li>System availability depends on infrastructure and configuration</li>
            </ul>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">5. Administrator Responsibilities</h2>
            <ul className="eg-body eg-content-list">
              <li>Ensure student and examination data is accurately imported</li>
              <li>Review verification results before making entry authorization decisions</li>
              <li>Handle verification failures and inconclusive results appropriately</li>
              <li>Maintain system configuration and access controls</li>
              <li>Ensure compliance with institutional policies and applicable regulations</li>
            </ul>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">6. Data Accuracy</h2>
            <p className="eg-body">
              The accuracy of verification results depends on the accuracy of
              the underlying data. Administrators are responsible for ensuring
              that student records, examination data, and hall ticket
              information are correct and up to date.
            </p>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">7. No Guarantees</h2>
            <p className="eg-body">
              ExamGuard is provided as a tool to assist examination
              administration. No specific guarantees are made regarding
              system accuracy, availability, or fitness for any particular
              purpose. The system is used at the discretion of the
              examination administration.
            </p>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">8. System Evolution</h2>
            <p className="eg-body">
              ExamGuard is under active development. Features described
              in the project roadmap are planned but not guaranteed.
              Current functionality is limited to what is documented
              in the system documentation. Future phases may introduce
              new capabilities including face verification, real-time
              monitoring, and additional security features.
            </p>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">9. Changes to Terms</h2>
            <p className="eg-body">
              These terms may be updated as the system evolves and its
              capabilities change. Significant changes to system
              functionality or verification processes will be documented.
            </p>
          </section>

          <section className="eg-content-section">
            <h2 className="eg-content-heading">10. Acceptance</h2>
            <p className="eg-body">
              By using the ExamGuard system, administrators acknowledge
              these terms and the system&apos;s capabilities and limitations
              as described in this document and the system documentation.
            </p>
          </section>
        </div>

        <div className="mt-16 pt-8" style={{ borderTop: "1px solid var(--border)" }}>
          <Link href="/" className="eg-btn">
            ← Back to ExamGuard
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
