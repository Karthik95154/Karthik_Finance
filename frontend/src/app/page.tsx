"use client";

import React from "react";
import Link from "next/link";
import PublicNavbar from "@/components/PublicNavbar";
import PublicFooter from "@/components/PublicFooter";
import {
  FileText,
  Brain,
  Calculator,
  ShieldCheck,
  Scale,
  BookOpen,
  ArrowRight,
  CheckCircle2,
  Lock,
  Layers,
  Sparkles,
  Search,
  Check,
} from "lucide-react";

export default function LandingPage() {
  const capabilities = [
    {
      icon: FileText,
      title: "AI Invoice Extraction",
      description:
        "Extracts header details, vendor metadata, line items, quantities, HSN codes, and tax breakdowns with zero data loss.",
      badge: "Vision-Language",
    },
    {
      icon: Brain,
      title: "COA Classification",
      description:
        "Maps line items to standard Chart of Accounts categories with confidence scoring and full audit trail.",
      badge: "Intelligent Mapping",
    },
    {
      icon: ShieldCheck,
      title: "GST & ITC Engine",
      description:
        "Deterministic Place of Supply resolution (intra vs inter-state) and rule-based Section 17(5) ITC blocking.",
      badge: "Statutory Compliance",
    },
    {
      icon: Scale,
      title: "TDS Assessment",
      description:
        "Automated Section 194C / 194J withholding analysis with clear finance approval and audit safeguards.",
      badge: "Withholding Tax",
    },
    {
      icon: Calculator,
      title: "Financial Validation",
      description:
        "Independent mathematical reconciliation between extracted invoice totals and calculated line-item taxes.",
      badge: "Deterministic Math",
    },
    {
      icon: BookOpen,
      title: "Double-Entry Journal",
      description:
        "Generates balanced accounting journals enforcing Debits == Credits without artificial balancing plugs.",
      badge: "Audit-Ready Ledger",
    },
  ];

  const workflowSteps = [
    {
      step: "01",
      title: "Invoice Ingestion",
      desc: "Upload PDF, PNG, or JPEG invoices. Stored securely with SHA-256 cryptographic deduplication.",
    },
    {
      step: "02",
      title: "Vision AI Extraction",
      desc: "Extracts vendor, invoice number, dates, line items, taxes, discounts, and custom fields.",
    },
    {
      step: "03",
      title: "Accounting & Tax Reasoning",
      desc: "Assigns Chart of Accounts expense/asset categories and assesses applicable TDS withholding rules.",
    },
    {
      step: "04",
      title: "Deterministic Validation",
      desc: "Rule-based engine checks Place of Supply, validates GST rates, and flags arithmetic discrepancies.",
    },
    {
      step: "05",
      title: "Double-Entry Journal Preview",
      desc: "Generates balanced debit/credit lines across expense, input tax, TDS payable, and vendor liability.",
    },
    {
      step: "06",
      title: "Finance Approval & Audit",
      desc: "Review discrepancies, override classifications with provenance tracking, and verify balanced books.",
    },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#ffffff",
      }}
    >
      <PublicNavbar />

      <main style={{ flex: 1 }}>
        {/* ============================================================
            HERO SECTION
            ============================================================ */}
        <section
          style={{
            padding: "80px 0 60px",
            background:
              "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0, 113, 227, 0.08), transparent 70%), #ffffff",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div className="container" style={{ textAlign: "center", maxWidth: "900px" }}>
            {/* Pill Badge */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "4px 12px",
                borderRadius: "20px",
                background: "rgba(0, 113, 227, 0.06)",
                border: "1px solid rgba(0, 113, 227, 0.15)",
                color: "var(--accent)",
                fontSize: "12px",
                fontWeight: "600",
                marginBottom: "24px",
              }}
            >
              <Sparkles size={14} />
              <span>Automated Invoice Processing & Double-Entry Accounting</span>
            </div>

            {/* Main Headline */}
            <h1
              style={{
                fontSize: "clamp(32px, 5vw, 54px)",
                fontWeight: "800",
                lineHeight: "1.15",
                letterSpacing: "-0.03em",
                color: "var(--text-primary)",
                marginBottom: "20px",
              }}
            >
              Autonomous AP Extraction.{" "}
              <span
                style={{
                  background: "linear-gradient(135deg, #0071e3 0%, #2563eb 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Deterministic Accounting.
              </span>
            </h1>

            {/* Subtitle */}
            <p
              style={{
                fontSize: "18px",
                lineHeight: "1.6",
                color: "var(--text-secondary)",
                marginBottom: "36px",
                maxWidth: "760px",
                margin: "0 auto 36px",
              }}
            >
              Transform raw invoices into audit-ready double-entry journal entries.
              Powered by Vision AI for extraction, guided by strict deterministic rules
              for GST, Section 17(5) ITC, and TDS compliance.
            </p>

            {/* CTAs */}
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gap: "14px",
                flexWrap: "wrap",
                marginBottom: "48px",
              }}
            >
              <Link
                href="/sign-up"
                className="btn btn-primary"
                style={{
                  padding: "12px 28px",
                  fontSize: "15px",
                  fontWeight: "600",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  borderRadius: "var(--radius-sm)",
                  boxShadow: "0 4px 14px rgba(0, 113, 227, 0.3)",
                }}
              >
                <span>Get Started Free</span>
                <ArrowRight size={16} />
              </Link>

              <Link
                href="/sign-in"
                className="btn btn-secondary"
                style={{
                  padding: "12px 26px",
                  fontSize: "15px",
                  fontWeight: "600",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                Sign In to Workspace
              </Link>
            </div>

            {/* Visual Hero Mockup: Dual Balanced Journal Card */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-lg)",
                boxShadow: "0 20px 40px -15px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0,0,0,0.03)",
                padding: "24px",
                textAlign: "left",
                maxWidth: "820px",
                margin: "0 auto",
              }}
            >
              {/* Card Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  paddingBottom: "16px",
                  borderBottom: "1px solid var(--border-subtle)",
                  marginBottom: "16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div
                    style={{
                      width: "10px",
                      height: "10px",
                      borderRadius: "50%",
                      background: "#16a34a",
                    }}
                  />
                  <span style={{ fontSize: "14px", fontWeight: "700" }}>
                    Live Journal Entry Preview
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      color: "var(--text-secondary)",
                      fontFamily: "monospace",
                    }}
                  >
                    INV-2026-0891
                  </span>
                </div>

                <span className="badge badge-success" style={{ fontSize: "11px" }}>
                  ✓ BALANCED (Dr = Cr)
                </span>
              </div>

              {/* Table Preview */}
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    fontSize: "12px",
                    borderCollapse: "collapse",
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        borderBottom: "1px solid var(--border-subtle)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      <th style={{ padding: "6px 8px" }}>Account</th>
                      <th style={{ padding: "6px 8px" }}>Type</th>
                      <th style={{ padding: "6px 8px", textAlign: "right" }}>Debit (Dr)</th>
                      <th style={{ padding: "6px 8px", textAlign: "right" }}>Credit (Cr)</th>
                      <th style={{ padding: "6px 8px" }}>Rule / Provenance</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "8px", fontWeight: "600" }}>
                        Cloud Hosting & Infrastructure
                      </td>
                      <td style={{ padding: "8px" }}>
                        <span className="badge badge-success" style={{ fontSize: "10px" }}>
                          EXPENSE
                        </span>
                      </td>
                      <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                        ₹15,000.00
                      </td>
                      <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                        -
                      </td>
                      <td style={{ padding: "8px", color: "var(--text-secondary)", fontSize: "11px" }}>
                        AI Predicted (ACC_1)
                      </td>
                    </tr>

                    <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "8px", fontWeight: "600" }}>Input CGST (9%)</td>
                      <td style={{ padding: "8px" }}>
                        <span className="badge badge-uploaded" style={{ fontSize: "10px" }}>
                          INPUT_TAX
                        </span>
                      </td>
                      <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                        ₹1,350.00
                      </td>
                      <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                        -
                      </td>
                      <td style={{ padding: "8px", color: "var(--text-secondary)", fontSize: "11px" }}>
                        Intra-State POS (Eligible)
                      </td>
                    </tr>

                    <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "8px", fontWeight: "600" }}>Input SGST (9%)</td>
                      <td style={{ padding: "8px" }}>
                        <span className="badge badge-uploaded" style={{ fontSize: "10px" }}>
                          INPUT_TAX
                        </span>
                      </td>
                      <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                        ₹1,350.00
                      </td>
                      <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                        -
                      </td>
                      <td style={{ padding: "8px", color: "var(--text-secondary)", fontSize: "11px" }}>
                        Intra-State POS (Eligible)
                      </td>
                    </tr>

                    <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "8px", fontWeight: "600" }}>
                        Accounts Payable (Vendor)
                      </td>
                      <td style={{ padding: "8px" }}>
                        <span className="badge badge-warning" style={{ fontSize: "10px" }}>
                          LIABILITY
                        </span>
                      </td>
                      <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                        -
                      </td>
                      <td
                        style={{
                          padding: "8px",
                          textAlign: "right",
                          fontFamily: "monospace",
                          fontWeight: "700",
                          color: "#166534",
                        }}
                      >
                        ₹17,700.00
                      </td>
                      <td style={{ padding: "8px", color: "var(--text-secondary)", fontSize: "11px" }}>
                        Net Vendor Obligation
                      </td>
                    </tr>

                    <tr
                      style={{
                        background: "#fafafa",
                        fontWeight: "700",
                        borderTop: "2px solid var(--border-subtle)",
                      }}
                    >
                      <td style={{ padding: "8px" }}>Reconciled Totals</td>
                      <td style={{ padding: "8px" }}>-</td>
                      <td
                        style={{
                          padding: "8px",
                          textAlign: "right",
                          fontFamily: "monospace",
                          color: "#15803d",
                        }}
                      >
                        ₹17,700.00
                      </td>
                      <td
                        style={{
                          padding: "8px",
                          textAlign: "right",
                          fontFamily: "monospace",
                          color: "#15803d",
                        }}
                      >
                        ₹17,700.00
                      </td>
                      <td
                        style={{
                          padding: "8px",
                          color: "#15803d",
                          fontSize: "11px",
                        }}
                      >
                        Net Difference: ₹0.00
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================
            HOW IT WORKS SECTION
            ============================================================ */}
        <section
          id="how-it-works"
          style={{
            padding: "80px 0",
            background: "#fafafa",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div className="container">
            <div style={{ textAlign: "center", maxWidth: "700px", margin: "0 auto 56px" }}>
              <h2
                style={{
                  fontSize: "30px",
                  fontWeight: "800",
                  letterSpacing: "-0.02em",
                  marginBottom: "12px",
                }}
              >
                How It Works
              </h2>
              <p style={{ fontSize: "16px", color: "var(--text-secondary)" }}>
                A 6-stage autonomous pipeline transforming raw invoice documents into
                validated accounting records without arithmetic hallucinations.
              </p>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "24px",
              }}
            >
              {workflowSteps.map((step, idx) => (
                <div
                  key={idx}
                  style={{
                    background: "#ffffff",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: "24px",
                    display: "flex",
                    flexDirection: "column",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      fontSize: "28px",
                      fontWeight: "800",
                      color: "rgba(0, 113, 227, 0.15)",
                      fontFamily: "monospace",
                      marginBottom: "8px",
                    }}
                  >
                    {step.step}
                  </div>
                  <h3
                    style={{
                      fontSize: "16px",
                      fontWeight: "700",
                      marginBottom: "8px",
                      color: "var(--text-primary)",
                    }}
                  >
                    {step.title}
                  </h3>
                  <p
                    style={{
                      fontSize: "13px",
                      lineHeight: "1.6",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {step.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ============================================================
            CORE CAPABILITIES SECTION
            ============================================================ */}
        <section
          id="capabilities"
          style={{
            padding: "80px 0",
            background: "#ffffff",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div className="container">
            <div style={{ textAlign: "center", maxWidth: "700px", margin: "0 auto 56px" }}>
              <h2
                style={{
                  fontSize: "30px",
                  fontWeight: "800",
                  letterSpacing: "-0.02em",
                  marginBottom: "12px",
                }}
              >
                Core Financial Capabilities
              </h2>
              <p style={{ fontSize: "16px", color: "var(--text-secondary)" }}>
                Built specifically for Indian Statutory Tax rules, double-entry ledgers,
                and high-accuracy accounts payable teams.
              </p>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: "24px",
              }}
            >
              {capabilities.map((item, idx) => {
                const Icon = item.icon;
                return (
                  <div
                    key={idx}
                    className="card"
                    style={{
                      padding: "24px",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      transition: "transform 0.15s ease, box-shadow 0.15s ease",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: "16px",
                        }}
                      >
                        <div
                          style={{
                            width: "38px",
                            height: "38px",
                            borderRadius: "8px",
                            background: "rgba(0, 113, 227, 0.08)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "var(--accent)",
                          }}
                        >
                          <Icon size={20} />
                        </div>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: "600",
                            padding: "3px 8px",
                            borderRadius: "4px",
                            background: "var(--border-subtle)",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {item.badge}
                        </span>
                      </div>
                      <h3
                        style={{
                          fontSize: "16px",
                          fontWeight: "700",
                          marginBottom: "8px",
                        }}
                      >
                        {item.title}
                      </h3>
                      <p
                        style={{
                          fontSize: "13px",
                          lineHeight: "1.6",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {item.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ============================================================
            FINANCE WORKFLOW / DETERMINISTIC PRINCIPLES SECTION
            ============================================================ */}
        <section
          id="workflow"
          style={{
            padding: "80px 0",
            background: "#fafafa",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div className="container" style={{ maxWidth: "960px" }}>
            <div
              style={{
                background: "#ffffff",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-lg)",
                padding: "40px",
              }}
            >
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "12px",
                  fontWeight: "700",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  color: "var(--accent)",
                  marginBottom: "12px",
                }}
              >
                <Lock size={14} />
                <span>Deterministic Architecture Guarantee</span>
              </div>
              <h2
                style={{
                  fontSize: "26px",
                  fontWeight: "800",
                  letterSpacing: "-0.02em",
                  marginBottom: "16px",
                }}
              >
                Why Finance Teams Trust This Engine
              </h2>
              <p
                style={{
                  fontSize: "15px",
                  lineHeight: "1.7",
                  color: "var(--text-secondary)",
                  marginBottom: "24px",
                }}
              >
                In standard accounting software, relying on LLMs for calculations causes
                hallucinated totals, tax rounding bugs, and unbalanced ledgers. Our
                architecture enforces a strict boundary:
              </p>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                  gap: "20px",
                }}
              >
                <div
                  style={{
                    background: "var(--bg-main)",
                    padding: "18px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      fontWeight: "700",
                      fontSize: "14px",
                      marginBottom: "6px",
                      color: "var(--accent)",
                    }}
                  >
                    <CheckCircle2 size={16} />
                    <span>AI For Perception Only</span>
                  </div>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                    Vision models parse complex multi-page layouts and OCR text. AI never performs
                    arithmetic or ledger balancing.
                  </p>
                </div>

                <div
                  style={{
                    background: "var(--bg-main)",
                    padding: "18px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      fontWeight: "700",
                      fontSize: "14px",
                      marginBottom: "6px",
                      color: "#166534",
                    }}
                  >
                    <CheckCircle2 size={16} />
                    <span>Deterministic Tax Rules</span>
                  </div>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                    Place of Supply, GST state codes, Section 17(5) blocking, and Section 194C/J TDS
                    follow hardcoded statutory logic.
                  </p>
                </div>

                <div
                  style={{
                    background: "var(--bg-main)",
                    padding: "18px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      fontWeight: "700",
                      fontSize: "14px",
                      marginBottom: "6px",
                      color: "#b45309",
                    }}
                  >
                    <CheckCircle2 size={16} />
                    <span>Zero Data Loss Guarantee</span>
                  </div>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                    Every unmapped field, line note, and raw VLM output is preserved in JSONB
                    for audit inspectability.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================
            FINAL CTA SECTION
            ============================================================ */}
        <section
          style={{
            padding: "80px 0",
            background: "#ffffff",
            textAlign: "center",
          }}
        >
          <div className="container" style={{ maxWidth: "700px" }}>
            <h2
              style={{
                fontSize: "32px",
                fontWeight: "800",
                letterSpacing: "-0.02em",
                marginBottom: "16px",
              }}
            >
              Ready to automate your invoice workspace?
            </h2>
            <p
              style={{
                fontSize: "16px",
                color: "var(--text-secondary)",
                marginBottom: "32px",
              }}
            >
              Sign in to explore your live invoice registry or create an account to start
              processing invoices in seconds.
            </p>
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                gap: "14px",
                flexWrap: "wrap",
              }}
            >
              <Link
                href="/sign-up"
                className="btn btn-primary"
                style={{
                  padding: "12px 28px",
                  fontSize: "15px",
                  fontWeight: "600",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                <span>Get Started</span>
                <ArrowRight size={16} />
              </Link>
              <Link
                href="/sign-in"
                className="btn btn-secondary"
                style={{
                  padding: "12px 26px",
                  fontSize: "15px",
                  fontWeight: "600",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                Sign In
              </Link>
            </div>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
