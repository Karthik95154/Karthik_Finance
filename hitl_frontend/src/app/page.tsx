"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listInvoices, getHitlHistory, InvoiceListItem } from "@/lib/api";
import { Activity, ShieldCheck, FileText, ChevronRight, CheckCircle2, History, Clock, Loader2, Sparkles } from "lucide-react";

export default function HitlDashboard() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"pending" | "history">("pending");
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [historyInvoices, setHistoryInvoices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [allData, historyData] = await Promise.all([
        listInvoices(),
        getHitlHistory().catch(() => []),
      ]);

      // Include all invoices that need review or are actively extracting
      const pendingInvoices = allData.filter(
        (inv) =>
          inv.status === "HITL_REVIEW" ||
          inv.status === "FINAL_HITL_REVIEW" ||
          inv.status === "PENDING" ||
          inv.status === "PROCESSING_VLM" ||
          inv.status === "PROCESSING_ACCOUNTING"
      );
      setInvoices(pendingInvoices);
      setHistoryInvoices(historyData || []);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReviewClick = (inv: InvoiceListItem) => {
    if (inv.status === "FINAL_HITL_REVIEW") {
      router.push(`/finance/invoices/${inv.id}/hitl/final`);
    } else {
      router.push(`/finance/invoices/${inv.id}/hitl/extraction`);
    }
  };

  if (loading) {
    return (
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "60px 24px", textAlign: "center", color: "#64748b" }}>
        Loading HITL Workspace &amp; History...
      </div>
    );
  }

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "40px 24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "28px", flexWrap: "wrap", gap: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ padding: "10px", backgroundColor: "#eff6ff", borderRadius: "10px", border: "1px solid #bfdbfe", color: "#2563eb" }}>
            <ShieldCheck size={32} />
          </div>
          <div>
            <h1 style={{ fontSize: "26px", fontWeight: "700", letterSpacing: "-0.02em", color: "#0f172a" }}>
              HITL Review Workspace
            </h1>
            <p style={{ color: "#64748b", fontSize: "14px" }}>
              Human-in-the-Loop Data &amp; Accounting Verification Engine
            </p>
          </div>
        </div>

        {/* Tab Switcher */}
        <div style={{ display: "flex", gap: "6px", background: "#f1f5f9", padding: "4px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
          <button
            onClick={() => setActiveTab("pending")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 16px",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: 600,
              background: activeTab === "pending" ? "#ffffff" : "transparent",
              color: activeTab === "pending" ? "#0f172a" : "#64748b",
              boxShadow: activeTab === "pending" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              border: "none",
              cursor: "pointer",
            }}
          >
            <Activity size={15} />
            <span>Pending Queue</span>
            {invoices.length > 0 && (
              <span style={{ backgroundColor: "#ef4444", color: "#fff", fontSize: "11px", padding: "1px 6px", borderRadius: "10px", fontWeight: 700 }}>
                {invoices.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("history")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 16px",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: 600,
              background: activeTab === "history" ? "#ffffff" : "transparent",
              color: activeTab === "history" ? "#0f172a" : "#64748b",
              boxShadow: activeTab === "history" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              border: "none",
              cursor: "pointer",
            }}
          >
            <History size={15} />
            <span>Review History</span>
            {historyInvoices.length > 0 && (
              <span style={{ backgroundColor: "#e2e8f0", color: "#475569", fontSize: "11px", padding: "1px 6px", borderRadius: "10px", fontWeight: 600 }}>
                {historyInvoices.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: "14px 18px", backgroundColor: "#fef2f2", color: "#b91c1c", borderRadius: "8px", marginBottom: "20px", border: "1px solid #fecaca", fontSize: "13px" }}>
          {error}
        </div>
      )}

      {/* TAB 1: PENDING QUEUE */}
      {activeTab === "pending" && (
        <div style={{ backgroundColor: "#fff", border: "1px solid #e2e8f0", borderRadius: "12px", overflow: "hidden", boxShadow: "0 2px 4px rgba(0, 0, 0, 0.04)" }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", backgroundColor: "#f8fafc", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ fontSize: "14px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px", color: "#1e293b", textTransform: "uppercase", letterSpacing: "0.02em" }}>
              <Activity size={16} color="#2563eb" />
              Invoices Awaiting Human Verification ({invoices.length})
            </h2>
          </div>

          {invoices.length === 0 ? (
            <div style={{ padding: "60px 24px", textAlign: "center", color: "#64748b" }}>
              <div style={{ display: "inline-flex", padding: "14px", backgroundColor: "#f0fdf4", borderRadius: "50%", marginBottom: "12px", border: "1px solid #bbf7d0" }}>
                <CheckCircle2 size={32} color="#16a34a" />
              </div>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#1e293b", marginBottom: "4px" }}>
                Queue is clear!
              </h3>
              <p style={{ fontSize: "13px" }}>Upload a new invoice in Port 3000 to start verification.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column" }}>
              {invoices.map((inv) => {
                const isProcessing = inv.status === "PENDING" || inv.status === "PROCESSING_VLM" || inv.status === "PROCESSING_ACCOUNTING";
                const isStage1 = inv.status === "HITL_REVIEW" || isProcessing;
                const isStage2 = inv.status === "FINAL_HITL_REVIEW";

                return (
                  <div 
                    key={inv.id}
                    style={{ 
                      display: "flex", 
                      alignItems: "center", 
                      justifyContent: "space-between",
                      padding: "18px 24px",
                      borderBottom: "1px solid #e2e8f0",
                      transition: "background-color 0.2s"
                    }}
                    className="hover:bg-slate-50"
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                      <div style={{ padding: "10px", backgroundColor: "#eff6ff", borderRadius: "8px", color: "#2563eb", border: "1px solid #dbeafe" }}>
                        <FileText size={22} />
                      </div>
                      <div>
                        <h3 style={{ fontWeight: 600, color: "#0f172a", marginBottom: "4px", fontSize: "15px" }}>
                          {inv.vendor_name || inv.file_name || "Uploaded Invoice"}
                        </h3>
                        <div style={{ display: "flex", gap: "12px", fontSize: "13px", color: "#64748b", flexWrap: "wrap" }}>
                          <span>Invoice: <strong style={{ color: "#334155" }}>{inv.invoice_number || "Unextracted"}</strong></span>
                          <span>•</span>
                          <span>Total: <strong style={{ color: "#334155" }}>{inv.total_amount ? `₹${inv.total_amount.toLocaleString()}` : "—"}</strong></span>
                          <span>•</span>
                          <span>Uploaded: {new Date(inv.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                      {isProcessing ? (
                        <span style={{ 
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "5px 12px", 
                          backgroundColor: "#fef3c7", 
                          color: "#92400e",
                          border: "1px solid #fde68a",
                          borderRadius: "999px",
                          fontSize: "12px",
                          fontWeight: 600
                        }}>
                          <Loader2 size={13} className="animate-spin" /> AI Extracting...
                        </span>
                      ) : (
                        <span style={{ 
                          padding: "5px 12px", 
                          backgroundColor: isStage1 ? "#eff6ff" : "#f0fdf4", 
                          color: isStage1 ? "#1d4ed8" : "#15803d",
                          border: `1px solid ${isStage1 ? "#bfdbfe" : "#bbf7d0"}`,
                          borderRadius: "999px",
                          fontSize: "12px",
                          fontWeight: 600
                        }}>
                          {isStage1 ? "STAGE 1: Extraction Review" : "STAGE 2: Final Accounting Review"}
                        </span>
                      )}
                      
                      <button 
                        onClick={() => handleReviewClick(inv)}
                        style={{ 
                          display: "flex", 
                          alignItems: "center", 
                          gap: "6px",
                          padding: "8px 16px", 
                          backgroundColor: "#0f172a", 
                          color: "#fff", 
                          borderRadius: "6px", 
                          fontSize: "13px", 
                          fontWeight: 600,
                          border: "none",
                          cursor: "pointer"
                        }}
                        className="hover:bg-slate-800 transition-colors"
                      >
                        Start Review <ChevronRight size={15} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: REVIEW HISTORY */}
      {activeTab === "history" && (
        <div style={{ backgroundColor: "#fff", border: "1px solid #e2e8f0", borderRadius: "12px", overflow: "hidden", boxShadow: "0 2px 4px rgba(0, 0, 0, 0.04)" }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", backgroundColor: "#f8fafc", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ fontSize: "14px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px", color: "#1e293b", textTransform: "uppercase", letterSpacing: "0.02em" }}>
              <History size={16} color="#16a34a" />
              Completed HITL Verifications ({historyInvoices.length})
            </h2>
          </div>

          {historyInvoices.length === 0 ? (
            <div style={{ padding: "60px 24px", textAlign: "center", color: "#64748b" }}>
              <Clock size={32} color="#94a3b8" style={{ marginBottom: "12px", display: "inline-block" }} />
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#1e293b", marginBottom: "4px" }}>
                No completed reviews yet
              </h3>
              <p style={{ fontSize: "13px" }}>Invoices approved in HITL Stage 1 &amp; Stage 2 will appear here with audit timestamps.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column" }}>
              {historyInvoices.map((inv) => (
                <div 
                  key={inv.id}
                  style={{ 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "space-between",
                    padding: "18px 24px",
                    borderBottom: "1px solid #e2e8f0",
                    transition: "background-color 0.2s"
                  }}
                  className="hover:bg-slate-50"
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                    <div style={{ padding: "10px", backgroundColor: "#f0fdf4", borderRadius: "8px", color: "#16a34a", border: "1px solid #bbf7d0" }}>
                      <CheckCircle2 size={22} />
                    </div>
                    <div>
                      <h3 style={{ fontWeight: 600, color: "#0f172a", marginBottom: "4px", fontSize: "15px" }}>
                        {inv.vendor_name || inv.file_name || "Unknown Vendor"}
                      </h3>
                      <div style={{ display: "flex", gap: "12px", fontSize: "13px", color: "#64748b", flexWrap: "wrap" }}>
                        <span>Invoice: <strong style={{ color: "#334155" }}>{inv.invoice_number || "INV"}</strong></span>
                        <span>•</span>
                        <span>Total: <strong style={{ color: "#334155" }}>{inv.total_amount ? `₹${inv.total_amount.toLocaleString()}` : "—"}</strong></span>
                        <span>•</span>
                        <span>Reviewed: {new Date(inv.updated_at || inv.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "4px" }}>
                      <span style={{ 
                        padding: "4px 10px", 
                        backgroundColor: "#f0fdf4", 
                        color: "#166534",
                        border: "1px solid #bbf7d0",
                        borderRadius: "999px",
                        fontSize: "11px",
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        gap: "4px"
                      }}>
                        <CheckCircle2 size={12} /> HITL COMPLETED
                      </span>
                      <span style={{ fontSize: "11px", color: "#64748b" }}>
                        {inv.status === "HITL_COMPLETED" 
                          ? "Pending Finance Approval (Port 3000)" 
                          : inv.status === "COMPLETED" 
                          ? "Finance Approved ✓" 
                          : inv.status === "EXPORTED" 
                          ? "Exported to Zoho ✓" 
                          : inv.status}
                      </span>
                    </div>

                    {inv.reviews && inv.reviews.length > 0 && (
                      <div style={{ display: "flex", gap: "6px" }}>
                        {inv.reviews.map((r: any, idx: number) => (
                          <span
                            key={idx}
                            title={`Approved on ${new Date(r.approved_at).toLocaleString()}`}
                            style={{
                              fontSize: "10px",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              backgroundColor: "#f1f5f9",
                              border: "1px solid #cbd5e1",
                              color: "#475569",
                              fontWeight: 600
                            }}
                          >
                            {r.stage === "EXTRACTION" ? "HITL 1 ✓" : "HITL 2 ✓"}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
