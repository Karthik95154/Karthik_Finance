"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { listInvoices, InvoiceListItem } from "@/lib/api";
import {
  FileCheck,
  Search,
  RefreshCw,
  Clock,
  ExternalLink,
  ShieldCheck,
  AlertCircle,
  Eye,
} from "lucide-react";

export default function InternalReviewQueuePage() {
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [stageFilter, setStageFilter] = useState<string>("ALL");

  const loadInvoices = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listInvoices();
      setInvoices(data);
    } catch (err: any) {
      setError(err.message || "Failed to load invoices from backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInvoices();
  }, []);

  // Filter queue invoices: focus on PENDING_REVIEW, PROCESSING, or COMPLETED review queues
  const reviewInvoices = invoices.filter((inv) => {
    const matchesSearch =
      (inv.invoice_number?.toLowerCase() || "").includes(searchTerm.toLowerCase()) ||
      (inv.vendor_name?.toLowerCase() || "").includes(searchTerm.toLowerCase()) ||
      (inv.file_name?.toLowerCase() || "").includes(searchTerm.toLowerCase());

    const isPendingReview = inv.approval_status === "PENDING_REVIEW" || !inv.approval_status;
    const isApproved = inv.approval_status === "APPROVED";
    const isExported = inv.export_status === "EXPORTED";
    const isProcessing =
      inv.status === "PENDING" ||
      inv.status === "PROCESSING_VLM" ||
      inv.status === "PROCESSING_ACCOUNTING";

    let matchesStage = true;
    if (stageFilter === "PENDING_REVIEW") {
      matchesStage = isPendingReview && inv.status === "COMPLETED";
    } else if (stageFilter === "PROCESSING") {
      matchesStage = isProcessing;
    } else if (stageFilter === "APPROVED") {
      matchesStage = isApproved && !isExported;
    } else if (stageFilter === "EXPORTED") {
      matchesStage = isExported;
    }

    return matchesSearch && matchesStage;
  });

  const pendingCount = invoices.filter(
    (inv) => (inv.approval_status === "PENDING_REVIEW" || !inv.approval_status) && inv.status === "COMPLETED"
  ).length;

  return (
    <AppShell
      title="Internal Finance Review (HITL Queue)"
      subtitle={`${pendingCount} Awaiting Internal Review`}
      actions={
        <button
          type="button"
          onClick={loadInvoices}
          disabled={loading}
          className="btn btn-secondary"
          style={{
            padding: "5px 10px",
            fontSize: "12px",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
          }}
          title="Refresh Queue"
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

      {/* Info Callout Banner */}
      <div
        style={{
          background: "#f0f7ff",
          border: "1px solid #bae6fd",
          borderRadius: "var(--radius-sm)",
          padding: "14px 18px",
          marginBottom: "20px",
          display: "flex",
          alignItems: "flex-start",
          gap: "12px",
        }}
      >
        <FileCheck size={20} color="#0284c7" style={{ flexShrink: 0, marginTop: "2px" }} />
        <div style={{ fontSize: "13px", color: "#0369a1", lineHeight: "1.5" }}>
          <strong style={{ display: "block", marginBottom: "2px" }}>
            Internal Human-in-the-Loop Review Stage (Port 3003)
          </strong>
          Finance users review AI extractions, verify Chart of Accounts classifications, confirm GST/ITC rules, adjust TDS deductions, and approve balanced General Ledger journals before invoices can be exported to Zoho Books.
        </div>
      </div>

      {/* Queue Toolbar: Search & Stage Filter */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ position: "relative", minWidth: "260px", maxWidth: "400px", flex: 1 }}>
          <Search
            size={14}
            style={{
              position: "absolute",
              left: "10px",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-tertiary)",
            }}
          />
          <input
            type="text"
            placeholder="Search queue by invoice #, vendor, or file..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="form-input"
            style={{ paddingLeft: "32px", fontSize: "13px" }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)" }}>
            Filter:
          </span>
          {[
            { key: "ALL", label: "All Items" },
            { key: "PENDING_REVIEW", label: `Pending Review (${pendingCount})` },
            { key: "PROCESSING", label: "Processing" },
            { key: "APPROVED", label: "Approved" },
            { key: "EXPORTED", label: "Zoho Synced" },
          ].map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setStageFilter(key)}
              className={stageFilter === key ? "btn btn-primary" : "btn btn-secondary"}
              style={{
                padding: "4px 10px",
                fontSize: "11px",
                fontWeight: "600",
                borderRadius: "var(--radius-sm)",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Queue Table */}
      <div className="card" style={{ padding: "0", overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: "48px", textAlign: "center", color: "var(--text-secondary)", fontSize: "14px" }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 12px" }} />
            <div>Loading review queue...</div>
          </div>
        ) : reviewInvoices.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "var(--text-secondary)" }}>
            <Search size={28} color="var(--text-tertiary)" style={{ margin: "0 auto 10px" }} />
            <div style={{ fontSize: "14px", fontWeight: "600", marginBottom: "4px" }}>
              No invoices matching queue criteria
            </div>
            <p style={{ fontSize: "12px" }}>
              Try adjusting your search query or filter selection.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: "13px", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr
                  style={{
                    background: "var(--bg-main)",
                    borderBottom: "1px solid var(--border-subtle)",
                    color: "var(--text-secondary)",
                    fontSize: "12px",
                    fontWeight: "600",
                  }}
                >
                  <th style={{ padding: "12px 16px" }}>Invoice / File</th>
                  <th style={{ padding: "12px 16px" }}>Vendor</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Grand Total (₹)</th>
                  <th style={{ padding: "12px 16px" }}>Pipeline State</th>
                  <th style={{ padding: "12px 16px" }}>Approval Status</th>
                  <th style={{ padding: "12px 16px" }}>Zoho Sync</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {reviewInvoices.map((inv) => (
                  <tr
                    key={inv.id}
                    style={{
                      borderBottom: "1px solid var(--border-subtle)",
                      transition: "background 0.1s ease",
                    }}
                    className="queue-table-row"
                  >
                    <td style={{ padding: "14px 16px" }}>
                      <div style={{ fontWeight: "600", color: "var(--text-primary)" }}>
                        {inv.invoice_number || inv.file_name}
                      </div>
                      {inv.invoice_number && (
                        <div style={{ fontSize: "11px", color: "var(--text-tertiary)", fontFamily: "monospace" }}>
                          {inv.file_name}
                        </div>
                      )}
                    </td>

                    <td style={{ padding: "14px 16px", color: "var(--text-secondary)" }}>
                      {inv.vendor_name || "—"}
                    </td>

                    <td
                      style={{
                        padding: "14px 16px",
                        textAlign: "right",
                        fontFamily: "monospace",
                        fontWeight: "600",
                        color: "var(--text-primary)",
                      }}
                    >
                      {typeof inv.total_amount === "number"
                        ? `₹${inv.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                        : "—"}
                    </td>

                    <td style={{ padding: "14px 16px" }}>
                      <span
                        className={`badge ${
                          inv.status === "COMPLETED"
                            ? "badge-success"
                            : inv.status === "FAILED"
                            ? "badge-danger"
                            : "badge-uploaded"
                        }`}
                        style={{ fontSize: "11px", fontWeight: "600" }}
                      >
                        {inv.status}
                      </span>
                    </td>

                    <td style={{ padding: "14px 16px" }}>
                      <span
                        className={`badge ${
                          inv.approval_status === "APPROVED"
                            ? "badge-success"
                            : inv.approval_status === "REJECTED"
                            ? "badge-danger"
                            : "badge-warning"
                        }`}
                        style={{ fontSize: "11px", fontWeight: "700" }}
                      >
                        {inv.approval_status === "APPROVED"
                          ? "Approved ✓"
                          : inv.approval_status === "REJECTED"
                          ? "Rejected ✗"
                          : "Pending Review"}
                      </span>
                    </td>

                    <td style={{ padding: "14px 16px" }}>
                      {inv.export_status === "EXPORTED" ? (
                        <span
                          className="badge badge-success"
                          style={{ fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "3px" }}
                        >
                          <ShieldCheck size={12} /> Synced
                        </span>
                      ) : (
                        <span className="badge badge-uploaded" style={{ fontSize: "11px" }}>
                          {inv.export_status || "NOT_EXPORTED"}
                        </span>
                      )}
                    </td>

                    <td style={{ padding: "14px 16px", textAlign: "right" }}>
                      <Link
                        href={`/finance/invoices/${inv.id}`}
                        className="btn btn-primary"
                        style={{
                          padding: "6px 12px",
                          fontSize: "12px",
                          fontWeight: "600",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <span>Review &amp; Edit</span>
                        <ExternalLink size={13} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <style jsx>{`
        .queue-table-row:hover {
          background: rgba(0, 113, 227, 0.02);
        }
      `}</style>
    </AppShell>
  );
}
