"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { listInvoices, InvoiceListItem } from "@/lib/api";
import {
  FileSpreadsheet,
  Search,
  UploadCloud,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  Filter,
  CheckCircle2,
  Clock,
  ExternalLink,
} from "lucide-react";

export default function InvoicesListPage() {
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

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

  // Filter invoices
  const filteredInvoices = invoices.filter((inv) => {
    const matchesSearch =
      (inv.invoice_number?.toLowerCase() || "").includes(searchTerm.toLowerCase()) ||
      (inv.vendor_name?.toLowerCase() || "").includes(searchTerm.toLowerCase()) ||
      (inv.file_name?.toLowerCase() || "").includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === "ALL" ||
      inv.status === statusFilter ||
      (statusFilter === "PROCESSING" &&
        (inv.status === "PENDING" ||
          inv.status === "PROCESSING_VLM" ||
          inv.status === "PROCESSING_ACCOUNTING"));

    return matchesSearch && matchesStatus;
  });

  return (
    <AppShell
      title="Invoice Registry"
      subtitle={`${invoices.length} Total Invoices`}
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
          title="Refresh Registry"
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

      {/* Control Bar: Search & Status Filter */}
      <div
        className="card"
        style={{
          padding: "14px 18px",
          marginBottom: "20px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "14px",
        }}
      >
        {/* Search Input */}
        <div style={{ position: "relative", minWidth: "260px", flex: 1 }}>
          <input
            type="text"
            className="form-input"
            placeholder="Search by invoice number, vendor, file..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              paddingLeft: "34px",
              fontSize: "13px",
              width: "100%",
            }}
          />
          <Search
            size={15}
            style={{
              position: "absolute",
              left: "11px",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-secondary)",
            }}
          />
        </div>

        {/* Filter Buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
            Status:
          </span>
          {["ALL", "COMPLETED", "PROCESSING", "FAILED"].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              className={statusFilter === st ? "btn btn-primary" : "btn btn-secondary"}
              style={{
                padding: "4px 10px",
                fontSize: "11px",
                fontWeight: "600",
                borderRadius: "var(--radius-sm)",
              }}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Invoice Table / Empty State */}
      <div className="card" style={{ padding: "0", overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: "48px", textAlign: "center", color: "var(--text-secondary)", fontSize: "14px" }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 12px" }} />
            <div>Loading stored invoices from Supabase...</div>
          </div>
        ) : invoices.length === 0 ? (
          /* Zero Invoices Empty State */
          <div style={{ padding: "60px 24px", textAlign: "center", maxWidth: "480px", margin: "0 auto" }}>
            <div
              style={{
                width: "56px",
                height: "56px",
                borderRadius: "50%",
                background: "rgba(0, 113, 227, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--accent)",
                margin: "0 auto 18px",
              }}
            >
              <UploadCloud size={28} />
            </div>
            <h2 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "8px" }}>
              Upload Invoice
            </h2>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "20px", lineHeight: "1.5" }}>
              Upload a PDF, PNG, or JPEG invoice to begin processing and double-entry journal generation.
            </p>
            <Link
              href="/finance/upload"
              className="btn btn-primary"
              style={{
                padding: "9px 20px",
                fontSize: "13px",
                fontWeight: "600",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <UploadCloud size={15} />
              <span>Upload Invoice</span>
            </Link>
          </div>
        ) : filteredInvoices.length === 0 ? (
          /* Filter Mismatch State */
          <div style={{ padding: "48px 24px", textAlign: "center", color: "var(--text-secondary)" }}>
            <Search size={28} color="var(--text-tertiary)" style={{ margin: "0 auto 10px" }} />
            <div style={{ fontSize: "14px", fontWeight: "600", marginBottom: "4px" }}>
              No matching invoices found
            </div>
            <p style={{ fontSize: "12px" }}>
              Try adjusting your search query or status filter.
            </p>
          </div>
        ) : (
          /* Invoices Table */
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
                  <th style={{ padding: "12px 16px" }}>Invoice / File Name</th>
                  <th style={{ padding: "12px 16px" }}>Vendor Name</th>
                  <th style={{ padding: "12px 16px" }}>Created Date</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Total Amount (₹)</th>
                  <th style={{ padding: "12px 16px" }}>Processing Status</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredInvoices.map((inv) => (
                  <tr
                    key={inv.id}
                    style={{
                      borderBottom: "1px solid var(--border-subtle)",
                      transition: "background 0.1s ease",
                    }}
                    className="invoice-table-row"
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

                    <td style={{ padding: "14px 16px", fontSize: "12px", color: "var(--text-secondary)" }}>
                      {new Date(inv.created_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
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

                    <td style={{ padding: "14px 16px", textAlign: "right" }}>
                      <Link
                        href={`/finance/invoices/${inv.id}`}
                        className="btn btn-secondary"
                        style={{
                          padding: "6px 12px",
                          fontSize: "12px",
                          fontWeight: "600",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <span>Open Workspace</span>
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
        .invoice-table-row:hover {
          background: rgba(0, 113, 227, 0.02);
        }
      `}</style>
    </AppShell>
  );
}
