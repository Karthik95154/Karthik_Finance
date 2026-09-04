import React from "react";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";

export default function PublicFooter() {
  return (
    <footer
      style={{
        background: "#ffffff",
        borderTop: "1px solid var(--border-subtle)",
        padding: "60px 0 36px",
        color: "var(--text-secondary)",
        fontSize: "13px",
      }}
    >
      <div className="container">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "40px",
            marginBottom: "48px",
          }}
        >
          {/* Col 1: Brand & Purpose */}
          <div style={{ maxWidth: "320px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "12px",
              }}
            >
              <div
                style={{
                  width: "26px",
                  height: "26px",
                  borderRadius: "6px",
                  background: "#0071e3",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#ffffff",
                }}
              >
                <ShieldCheck size={16} />
              </div>
              <span
                style={{
                  fontSize: "17px",
                  fontWeight: "700",
                  letterSpacing: "-0.02em",
                  color: "var(--text-primary)",
                }}
              >
                Finance Module
              </span>
            </div>
            <p
              style={{
                lineHeight: "1.6",
                color: "var(--text-secondary)",
                marginBottom: "16px",
              }}
            >
              Automated invoice extraction, chart of accounts classification,
              deterministic GST/ITC calculation, TDS assessment, and balanced
              double-entry journal generation.
            </p>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "12px",
                fontWeight: "600",
                color: "#166534",
                background: "#f0fdf4",
                padding: "4px 10px",
                borderRadius: "20px",
                border: "1px solid #bbf7d0",
              }}
            >
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: "#16a34a",
                }}
              />
              <span>Zero LLM Ledger Guarantee</span>
            </div>
          </div>

          {/* Col 2: Pipeline Stages */}
          <div>
            <h4
              style={{
                fontSize: "13px",
                fontWeight: "700",
                color: "var(--text-primary)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: "16px",
              }}
            >
              Pipeline Architecture
            </h4>
            <ul
              style={{
                listStyle: "none",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
              }}
            >
              <li>Stage 1: Document Ingestion & Storage</li>
              <li>Stage 2: Vision-Language Model Extraction</li>
              <li>Stage 3: COA & TDS Reasoning</li>
              <li>Stage 4: Deterministic GST & ITC Engine</li>
              <li>Stage 5: Mathematical Reconciliation</li>
              <li>Stage 6: Double-Entry Journal Preview</li>
            </ul>
          </div>

          {/* Col 3: Compliance & Standards */}
          <div>
            <h4
              style={{
                fontSize: "13px",
                fontWeight: "700",
                color: "var(--text-primary)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: "16px",
              }}
            >
              Compliance Standards
            </h4>
            <ul
              style={{
                listStyle: "none",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
              }}
            >
              <li>CGST & SGST Rules (Sec 12 / 13)</li>
              <li>IGST Inter-State Rules (Sec 7 / 8)</li>
              <li>ITC Blocking Rules (Sec 17(5))</li>
              <li>Income Tax TDS (Sec 194C / 194J)</li>
              <li>Place of Supply Determination</li>
              <li>Double-Entry Ledger Balancing</li>
            </ul>
          </div>

          {/* Col 4: Quick Navigation */}
          <div>
            <h4
              style={{
                fontSize: "13px",
                fontWeight: "700",
                color: "var(--text-primary)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: "16px",
              }}
            >
              Navigation
            </h4>
            <ul
              style={{
                listStyle: "none",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
              }}
            >
              <li>
                <Link
                  href="/sign-in"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Sign In
                </Link>
              </li>
              <li>
                <Link
                  href="/sign-up"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Create Account
                </Link>
              </li>
              <li>
                <Link
                  href="/dashboard"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Finance Dashboard
                </Link>
              </li>
              <li>
                <Link
                  href="/finance/invoices"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Invoice Registry
                </Link>
              </li>
              <li>
                <Link
                  href="/finance/upload"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Upload Invoice
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div
          style={{
            borderTop: "1px solid var(--border-subtle)",
            paddingTop: "24px",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "16px",
            fontSize: "12px",
            color: "var(--text-tertiary)",
          }}
        >
          <div>
            © {new Date().getFullYear()} Finance Module. Autonomous Accounts Payable
            & Audit-Ready Accounting.
          </div>
          <div style={{ display: "flex", gap: "20px" }}>
            <span>Deterministic Math</span>
            <span>•</span>
            <span>Zero Hallucination</span>
            <span>•</span>
            <span>Audit Proof</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
