"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import {
  listInvoices,
  InvoiceListItem,
  getHealth,
  HealthResponse,
} from "@/lib/api";
import {
  FileSpreadsheet,
  AlertCircle,
  CheckCircle2,
  Clock,
  ArrowRight,
  TrendingUp,
  ShieldAlert,
  ShieldCheck,
  BookOpen,
  Scale,
  UploadCloud,
  Layers,
  ChevronRight,
  RefreshCw,
} from "lucide-react";

export default function DashboardPage() {
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [listData, healthData] = await Promise.all([
        listInvoices().catch(() => []),
        getHealth().catch(() => null),
      ]);
      setInvoices(listData);
      setHealth(healthData);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  // Compute real metrics from backend invoice data
  const totalInvoices = invoices.length;
  const processingCount = invoices.filter(
    (inv) =>
      inv.status === "PENDING" ||
      inv.status === "PROCESSING_VLM" ||
      inv.status === "PROCESSING_ACCOUNTING"
  ).length;
  const failedCount = invoices.filter(
    (inv) => inv.status === "FAILED" || inv.accounting_status === "FAILED"
  ).length;
  const completedCount = invoices.filter(
    (inv) => inv.status === "COMPLETED"
  ).length;

  const totalValue = invoices.reduce((acc, inv) => {
    const val = typeof inv.total_amount === "number" ? inv.total_amount : 0;
    return acc + val;
  }, 0);

  // Invoices requiring attention
  const attentionInvoices = invoices.filter(
    (inv) =>
      inv.status === "FAILED" ||
      inv.accounting_status === "FAILED" ||
      inv.status === "PENDING"
  );

  return (
    <AppShell
      title="Finance Overview"
      subtitle="AP Operations & Ledger Summary"
      actions={
        <button
          type="button"
          onClick={fetchDashboardData}
          disabled={loading}
          className="btn btn-secondary"
          style={{
            padding: "5px 10px",
            fontSize: "12px",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
          }}
          title="Refresh Dashboard Data"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          <span>Refresh</span>
        </button>
      }
    >
      {/* Error Alert */}
      {error && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "var(--radius-sm)",
            padding: "12px 16px",
            marginBottom: "20px",
            fontSize: "13px",
            color: "#991b1b",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* ============================================================
          TOP SUMMARY METRICS CARDS (REAL DATA ONLY)
          ============================================================ */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "16px",
          marginBottom: "24px",
        }}
      >
        {/* Total Invoices */}
        <div className="card" style={{ padding: "18px 20px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "8px",
            }}
          >
            <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
              Total Invoices
            </span>
            <FileSpreadsheet size={16} color="var(--text-tertiary)" />
          </div>
          <div
            style={{
              fontSize: "24px",
              fontWeight: "700",
              color: "var(--text-primary)",
              fontFamily: "monospace",
            }}
          >
            {loading ? "..." : totalInvoices}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
            Stored in PostgreSQL
          </div>
        </div>

        {/* Total Invoice Value */}
        <div className="card" style={{ padding: "18px 20px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "8px",
            }}
          >
            <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
              Total Gross Obligation
            </span>
            <TrendingUp size={16} color="#15803d" />
          </div>
          <div
            style={{
              fontSize: "22px",
              fontWeight: "700",
              color: "#166534",
              fontFamily: "monospace",
            }}
          >
            {loading
              ? "..."
              : `₹${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
            Sum of extracted totals
          </div>
        </div>

        {/* Completed Invoices */}
        <div className="card" style={{ padding: "18px 20px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "8px",
            }}
          >
            <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
              Processed Invoices
            </span>
            <CheckCircle2 size={16} color="#15803d" />
          </div>
          <div
            style={{
              fontSize: "24px",
              fontWeight: "700",
              color: "var(--text-primary)",
              fontFamily: "monospace",
            }}
          >
            {loading ? "..." : completedCount}
          </div>
          <div style={{ fontSize: "11px", color: "#15803d", marginTop: "4px", fontWeight: "500" }}>
            Ready for Finance Review
          </div>
        </div>

        {/* Processing / Queued */}
        <div className="card" style={{ padding: "18px 20px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "8px",
            }}
          >
            <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
              In Processing Pipeline
            </span>
            <Clock size={16} color="#ca8a04" />
          </div>
          <div
            style={{
              fontSize: "24px",
              fontWeight: "700",
              color: processingCount > 0 ? "#b45309" : "var(--text-primary)",
              fontFamily: "monospace",
            }}
          >
            {loading ? "..." : processingCount}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
            AI Extraction / COA queue
          </div>
        </div>

        {/* Attention / Failed */}
        <div className="card" style={{ padding: "18px 20px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "8px",
            }}
          >
            <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
              Attention Required
            </span>
            <ShieldAlert size={16} color={failedCount > 0 ? "#dc2626" : "var(--text-tertiary)"} />
          </div>
          <div
            style={{
              fontSize: "24px",
              fontWeight: "700",
              color: failedCount > 0 ? "#b91c1c" : "var(--text-primary)",
              fontFamily: "monospace",
            }}
          >
            {loading ? "..." : failedCount}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
            {failedCount > 0 ? "Extraction / validation alert" : "Zero active failures"}
          </div>
        </div>
      </div>

      {/* ============================================================
          MAIN CONTENT GRID: RECENT INVOICES & ATTENTION REQUIRED
          ============================================================ */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr",
          gap: "24px",
        }}
        className="dashboard-main-grid"
      >
        {/* Left Column: Recent Activity Table */}
        <div className="card" style={{ padding: "20px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "16px",
            }}
          >
            <div>
              <h2 style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-primary)" }}>
                Recent Invoices
              </h2>
              <p style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                Latest invoices stored and processed by the system
              </p>
            </div>
            <Link
              href="/finance/invoices"
              style={{
                fontSize: "12px",
                fontWeight: "600",
                color: "var(--accent)",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <span>View All</span>
              <ChevronRight size={14} />
            </Link>
          </div>

          {loading ? (
            <div style={{ padding: "32px", textAlign: "center", color: "var(--text-secondary)", fontSize: "13px" }}>
              Loading invoice activity...
            </div>
          ) : invoices.length === 0 ? (
            <div
              style={{
                padding: "36px 20px",
                textAlign: "center",
                background: "var(--bg-main)",
                borderRadius: "var(--radius-sm)",
                border: "1px dashed var(--border-strong)",
              }}
            >
              <UploadCloud size={32} color="var(--text-tertiary)" style={{ margin: "0 auto 10px" }} />
              <div style={{ fontSize: "14px", fontWeight: "600", marginBottom: "4px" }}>
                No invoices processed yet
              </div>
              <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "16px" }}>
                Upload a PDF, PNG, or JPEG invoice to begin autonomous extraction and journal generation.
              </p>
              <Link href="/finance/upload" className="btn btn-primary" style={{ padding: "6px 14px", fontSize: "13px" }}>
                Upload First Invoice
              </Link>
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse" }}>
                <thead>
                  <tr
                    style={{
                      borderBottom: "1px solid var(--border-subtle)",
                      color: "var(--text-secondary)",
                      textAlign: "left",
                    }}
                  >
                    <th style={{ padding: "8px" }}>Invoice / File</th>
                    <th style={{ padding: "8px" }}>Vendor</th>
                    <th style={{ padding: "8px", textAlign: "right" }}>Amount (₹)</th>
                    <th style={{ padding: "8px" }}>Status</th>
                    <th style={{ padding: "8px", textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.slice(0, 7).map((inv) => (
                    <tr
                      key={inv.id}
                      style={{
                        borderBottom: "1px solid var(--border-subtle)",
                        transition: "background 0.1s ease",
                      }}
                    >
                      <td style={{ padding: "10px 8px" }}>
                        <div style={{ fontWeight: "600", color: "var(--text-primary)" }}>
                          {inv.invoice_number || inv.file_name}
                        </div>
                        <div style={{ fontSize: "10px", color: "var(--text-tertiary)", fontFamily: "monospace" }}>
                          {new Date(inv.created_at).toLocaleDateString()}
                        </div>
                      </td>
                      <td style={{ padding: "10px 8px", color: "var(--text-secondary)" }}>
                        {inv.vendor_name || "—"}
                      </td>
                      <td
                        style={{
                          padding: "10px 8px",
                          textAlign: "right",
                          fontFamily: "monospace",
                          fontWeight: "600",
                        }}
                      >
                        {typeof inv.total_amount === "number"
                          ? `₹${inv.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                          : "—"}
                      </td>
                      <td style={{ padding: "10px 8px" }}>
                        <span
                          className={`badge ${
                            inv.status === "COMPLETED"
                              ? "badge-success"
                              : inv.status === "FAILED"
                              ? "badge-danger"
                              : "badge-uploaded"
                          }`}
                          style={{ fontSize: "10px" }}
                        >
                          {inv.status}
                        </span>
                      </td>
                      <td style={{ padding: "10px 8px", textAlign: "right" }}>
                        <Link
                          href={`/finance/invoices/${inv.id}`}
                          className="btn btn-secondary"
                          style={{ padding: "4px 8px", fontSize: "11px" }}
                        >
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column: Attention Required & Statutory Info */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Attention Required Card */}
          <div className="card" style={{ padding: "20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
              <ShieldAlert size={16} color="#b45309" />
              <h3 style={{ fontSize: "14px", fontWeight: "700" }}>Attention Required</h3>
            </div>

            {attentionInvoices.length === 0 ? (
              <div
                style={{
                  background: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  borderRadius: "var(--radius-sm)",
                  padding: "12px",
                  fontSize: "12px",
                  color: "#166534",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <CheckCircle2 size={16} />
                <span>All invoices are in healthy status. No critical pipeline errors.</span>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {attentionInvoices.slice(0, 4).map((inv) => (
                  <Link
                    key={inv.id}
                    href={`/finance/invoices/${inv.id}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      borderRadius: "var(--radius-sm)",
                      background: "#fef2f2",
                      border: "1px solid #fecaca",
                      fontSize: "12px",
                      textDecoration: "none",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: "600", color: "#991b1b" }}>
                        {inv.file_name}
                      </div>
                      <div style={{ fontSize: "10px", color: "#b91c1c" }}>
                        Status: {inv.status} {inv.accounting_status ? `(${inv.accounting_status})` : ""}
                      </div>
                    </div>
                    <ArrowRight size={14} color="#991b1b" />
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Statutory Engine Reference Card */}
          <div className="card" style={{ padding: "20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
              <Scale size={16} color="var(--accent)" />
              <h3 style={{ fontSize: "14px", fontWeight: "700" }}>Statutory Rules</h3>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
              <div style={{ marginBottom: "8px" }}>
                <strong>GST Engine:</strong> Validates Place of Supply (POS) state codes and enforces CGST+SGST vs IGST split.
              </div>
              <div style={{ marginBottom: "8px" }}>
                <strong>ITC Sec 17(5):</strong> Detects blocked credits for motor vehicles, catering, personal use, and gifts.
              </div>
              <div>
                <strong>TDS Withholding:</strong> Evaluates Section 194C / 194J applicability with finance gating.
              </div>
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        @media (max-width: 960px) {
          .dashboard-main-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </AppShell>
  );
}
