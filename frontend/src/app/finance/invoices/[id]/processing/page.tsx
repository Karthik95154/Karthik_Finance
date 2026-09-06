"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getInvoiceStatus, submitPeriodDecision, InvoiceStatus, invalidateInvoicesCache } from "@/lib/api";
import { CheckCircle2, Loader2, AlertCircle, ArrowLeft, Sparkles, Clock, Calendar, AlertTriangle } from "lucide-react";

export default function InvoiceProcessingPage() {
  const params = useParams();
  const router = useRouter();
  const invoiceId = params?.id as string;

  const [statusData, setStatusData] = useState<InvoiceStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollCount, setPollCount] = useState(0);
  const [isDeciding, setIsDeciding] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  useEffect(() => {
    if (!invoiceId) return;

    let isMounted = true;
    let timer: NodeJS.Timeout;

    async function checkStatus() {
      try {
        const data = await getInvoiceStatus(invoiceId);
        if (!isMounted) return;

        setStatusData(data);
        setPollCount((prev) => prev + 1);

        const isApproved =
          data.status === "APPROVED" ||
          data.approval_status === "APPROVED" ||
          (data.status === "COMPLETED" && data.approval_status === "APPROVED");

        if (isApproved) {
          // Both HITL approvals completed -> invoice is officially released to customer
          invalidateInvoicesCache();
          setTimeout(() => {
            router.push(`/finance/invoices/${invoiceId}`);
          }, 1200);
        } else if (data.status === "CANCELLED" || data.period_decision === "CANCELLED") {
          // Processing cancelled safely
          setError(data.error_message || "Invoice processing cancelled by user (Previous Financial Year).");
        } else if (data.status === "FAILED" || data.accounting_status === "FAILED") {
          setError(data.error_message || "Invoice processing encountered an issue.");
        } else {
          // Continuously poll every 2.5s across all stages (VLM -> HITL 1 -> COA -> HITL 2)
          timer = setTimeout(checkStatus, 2500);
        }
      } catch (err: any) {
        if (!isMounted) return;
        console.warn("Status poll error:", err);
        timer = setTimeout(checkStatus, 3000);
      }
    }

    checkStatus();

    return () => {
      isMounted = false;
      if (timer) clearTimeout(timer);
    };
  }, [invoiceId, router]);

  const handlePeriodDecision = async (decision: "CONTINUE" | "CANCEL") => {
    if (!invoiceId) return;
    setIsDeciding(true);
    setDecisionError(null);
    try {
      const res = await submitPeriodDecision(invoiceId, decision);
      // Immediately refresh status
      const updated = await getInvoiceStatus(invoiceId);
      setStatusData(updated);
      if (decision === "CANCEL") {
        setError("Invoice processing cancelled by user (Previous Financial Year).");
      }
    } catch (err: any) {
      setDecisionError(err?.message || "Failed to submit decision. Please try again.");
    } finally {
      setIsDeciding(false);
    }
  };

  const currentStatus = statusData?.status || "PROCESSING_VLM";
  const approvalStatus = statusData?.approval_status;

  // 5 Explicit Lifecycle States:
  // State 1: PROCESSING_VLM
  const isVlmRunning = currentStatus === "UPLOADED" || currentStatus === "PROCESSING_VLM" || currentStatus === "PENDING";

  // State 2: HITL_REVIEW (Waiting for HITL Approval #1)
  const isWaitingHitl1 = currentStatus === "HITL_REVIEW";

  // State 3: ACCOUNTING_PROCESSING (Running downstream COA/TDS after Approval #1)
  const isAccountingRunning = currentStatus === "ACCOUNTING_PROCESSING";

  // State 4: FINAL_HITL_REVIEW (Waiting for HITL Approval #2)
  const isWaitingHitl2 = currentStatus === "FINAL_HITL_REVIEW" || currentStatus === "PENDING_FINANCE_APPROVAL";

  // State 5: APPROVED (Completed after HITL Approval #2)
  const isApproved =
    currentStatus === "APPROVED" ||
    approvalStatus === "APPROVED" ||
    (currentStatus === "COMPLETED" && approvalStatus === "APPROVED");

  // Step milestones for visual timeline:
  const isVlmDone = !isVlmRunning;
  const isHitl1Done = isAccountingRunning || isWaitingHitl2 || isApproved;
  const isAccountingDone = isWaitingHitl2 || isApproved;
  const isHitl2Done = isApproved;

  // Dynamic header text based on exact active stage
  const getHeaderTitle = () => {
    if (isApproved) return "Invoice Approved & Ready!";
    if (isWaitingHitl2) return "Awaiting Final Finance Approval";
    if (isAccountingRunning) return "Classifying Accounting & Taxes";
    if (isWaitingHitl1) return "Extraction Complete — In Review";
    if (isVlmRunning) return "Qwen3-VL Model Running";
    return "Processing Invoice";
  };

  const getHeaderSubtitle = () => {
    if (isApproved) return "Final accounting review approved. Opening invoice workspace...";
    if (isWaitingHitl2) return "Accounting, TDS & double-entry journal verified. Waiting for final finance approval.";
    if (isAccountingRunning) return "Classifying line items against Chart of Accounts (COA) and evaluating TDS rules.";
    if (isWaitingHitl1) return "AI extraction completed. Internal finance team is reviewing extracted invoice data.";
    if (isVlmRunning) return "Qwen3-VL is extracting semantic tables, vendor details, header fields and line items.";
    return "Extracting and analyzing invoice details.";
  };

  return (
    <div className="container" style={{ maxWidth: "640px", paddingTop: "60px", paddingBottom: "80px" }}>
      <div className="card" style={{ padding: "40px 32px", textAlign: "center", boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01)" }}>
        {statusData?.status === "FAILED" || statusData?.accounting_status === "FAILED" ? (
          <div>
            <div
              style={{
                width: "56px",
                height: "56px",
                borderRadius: "50%",
                background: "var(--danger-bg)",
                color: "var(--danger)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 16px",
              }}
            >
              <AlertCircle size={32} />
            </div>

            <h1 style={{ fontSize: "22px", fontWeight: "700", marginBottom: "8px" }}>
              Unable to Complete Processing
            </h1>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "24px" }}>
              The pipeline encountered an issue processing this document.
            </p>

            {error && (
              <div
                style={{
                  background: "var(--bg-main)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-sm)",
                  padding: "14px",
                  textAlign: "left",
                  fontSize: "13px",
                  color: "var(--danger)",
                  marginBottom: "24px",
                  wordBreak: "break-word",
                }}
              >
                {error}
              </div>
            )}

            <button
              onClick={() => router.push("/finance/upload")}
              className="btn btn-secondary"
              style={{ width: "100%", padding: "12px" }}
            >
              <ArrowLeft size={16} />
              <span>Back to Upload</span>
            </button>
          </div>
        ) : (
          <div>
            <div
              style={{
                width: "64px",
                height: "64px",
                borderRadius: "50%",
                background: isApproved ? "#f0fdf4" : (isWaitingHitl1 || isWaitingHitl2) ? "#fef3c7" : "#f0f7ff",
                color: isApproved ? "var(--success)" : (isWaitingHitl1 || isWaitingHitl2) ? "#b45309" : "var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 20px",
                transition: "all 0.3s ease",
              }}
            >
              {isApproved ? (
                <CheckCircle2 size={36} color="#16a34a" />
              ) : (isWaitingHitl1 || isWaitingHitl2) ? (
                <Clock size={32} color="#b45309" />
              ) : (
                <Loader2 size={36} className="animate-spin" style={{ animation: "spin 1.5s linear infinite" }} />
              )}
            </div>

            <h1 style={{ fontSize: "24px", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "8px" }}>
              {getHeaderTitle()}
            </h1>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "20px", minHeight: "36px" }}>
              {getHeaderSubtitle()}
            </p>

            {/* Accounting Period Indicator Badge */}
            {statusData?.period_message && (
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "4px 12px",
                  borderRadius: "16px",
                  fontSize: "12px",
                  fontWeight: "500",
                  marginBottom: "20px",
                  background: statusData.period_category === "PREVIOUS_FINANCIAL_YEAR" ? "#fef2f2" : "#f1f5f9",
                  color: statusData.period_category === "PREVIOUS_FINANCIAL_YEAR" ? "#b91c1c" : "#475569",
                  border: `1px solid ${statusData.period_category === "PREVIOUS_FINANCIAL_YEAR" ? "#fecaca" : "#e2e8f0"}`,
                }}
              >
                <Calendar size={13} />
                <span>{statusData.period_message}</span>
              </div>
            )}

            {/* Previous Financial Year Customer Confirmation Dialog */}
            {statusData?.period_category === "PREVIOUS_FINANCIAL_YEAR" &&
              statusData?.period_decision === "PENDING" && (
                <div
                  style={{
                    background: "#fff1f2",
                    border: "1px solid #fecdd3",
                    borderRadius: "var(--radius-md)",
                    padding: "20px",
                    textAlign: "left",
                    marginBottom: "24px",
                    boxShadow: "0 2px 6px rgba(225, 29, 72, 0.08)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", marginBottom: "16px" }}>
                    <div
                      style={{
                        background: "#ffe4e6",
                        color: "#e11d48",
                        borderRadius: "50%",
                        width: "32px",
                        height: "32px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                        marginTop: "2px",
                      }}
                    >
                      <AlertTriangle size={18} />
                    </div>
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: "700", color: "#9f1239", marginBottom: "4px" }}>
                        Previous Financial Year Invoice
                      </div>
                      <div style={{ fontSize: "13px", color: "#4c0519", lineHeight: "1.5" }}>
                        This invoice belongs to a previous financial year. Do you want to continue processing?
                      </div>
                    </div>
                  </div>

                  {decisionError && (
                    <div
                      style={{
                        background: "#fee2e2",
                        color: "#991b1b",
                        fontSize: "12px",
                        padding: "8px 12px",
                        borderRadius: "4px",
                        marginBottom: "12px",
                      }}
                    >
                      {decisionError}
                    </div>
                  )}

                  <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      disabled={isDeciding}
                      onClick={() => handlePeriodDecision("CANCEL")}
                      style={{
                        padding: "8px 16px",
                        borderRadius: "6px",
                        border: "1px solid #cbd5e1",
                        background: "#ffffff",
                        color: "#475569",
                        fontSize: "13px",
                        fontWeight: "600",
                        cursor: isDeciding ? "not-allowed" : "pointer",
                        opacity: isDeciding ? 0.6 : 1,
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={isDeciding}
                      onClick={() => handlePeriodDecision("CONTINUE")}
                      style={{
                        padding: "8px 18px",
                        borderRadius: "6px",
                        border: "none",
                        background: "#e11d48",
                        color: "#ffffff",
                        fontSize: "13px",
                        fontWeight: "600",
                        cursor: isDeciding ? "not-allowed" : "pointer",
                        opacity: isDeciding ? 0.6 : 1,
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      {isDeciding && <Loader2 size={14} className="animate-spin" />}
                      <span>Continue Processing</span>
                    </button>
                  </div>
                </div>
              )}

            {/* Step Progress Timeline */}
            <div
              style={{
                background: "var(--bg-main)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "24px",
                textAlign: "left",
                marginBottom: "24px",
                display: "flex",
                flexDirection: "column",
                gap: "20px",
              }}
            >
              {/* Step 1: Upload Completed */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                <CheckCircle2 size={22} color="#16a34a" style={{ flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-primary)" }}>
                    1. Upload Completed
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Invoice file securely stored & registered
                  </div>
                </div>
              </div>

              {/* Step 2: Qwen3-VL Extraction */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px", opacity: isVlmDone || isVlmRunning ? 1 : 0.4 }}>
                {isVlmDone ? (
                  <CheckCircle2 size={22} color="#16a34a" style={{ flexShrink: 0 }} />
                ) : isVlmRunning ? (
                  <div
                    style={{
                      width: "22px",
                      height: "22px",
                      borderRadius: "50%",
                      border: "2.5px solid var(--accent)",
                      borderTopColor: "transparent",
                      animation: "spin 1s linear infinite",
                      flexShrink: 0,
                    }}
                  />
                ) : (
                  <div style={{ width: "22px", height: "22px", borderRadius: "50%", border: "2px solid var(--border-strong)", flexShrink: 0 }} />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600", color: isVlmRunning ? "var(--accent)" : "var(--text-primary)" }}>
                    2. Qwen3-VL Extraction {isVlmRunning && <span style={{ fontSize: "12px", fontWeight: "400" }}>(Running...)</span>}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Extracting semantic fields, vendor details & line items
                  </div>
                </div>
              </div>

              {/* Step 3: HITL Review #1 */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px", opacity: isHitl1Done || isWaitingHitl1 ? 1 : 0.4 }}>
                {isHitl1Done ? (
                  <CheckCircle2 size={22} color="#16a34a" style={{ flexShrink: 0 }} />
                ) : isWaitingHitl1 ? (
                  <div
                    style={{
                      width: "22px",
                      height: "22px",
                      borderRadius: "50%",
                      background: "#fef3c7",
                      color: "#b45309",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Clock size={15} />
                  </div>
                ) : (
                  <div style={{ width: "22px", height: "22px", borderRadius: "50%", border: "2px solid var(--border-strong)", flexShrink: 0 }} />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600", color: isWaitingHitl1 ? "#b45309" : "var(--text-primary)" }}>
                    3. Extraction Review (HITL #1) {isWaitingHitl1 && <span style={{ fontSize: "12px", fontWeight: "600" }}>(In Review)</span>}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Internal verification of extracted header, vendor and line items
                  </div>
                </div>
              </div>

              {/* Step 4: Accounting & Taxes */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px", opacity: isAccountingDone || isAccountingRunning ? 1 : 0.4 }}>
                {isAccountingDone ? (
                  <CheckCircle2 size={22} color="#16a34a" style={{ flexShrink: 0 }} />
                ) : isAccountingRunning ? (
                  <div
                    style={{
                      width: "22px",
                      height: "22px",
                      borderRadius: "50%",
                      border: "2.5px solid var(--accent)",
                      borderTopColor: "transparent",
                      animation: "spin 1s linear infinite",
                      flexShrink: 0,
                    }}
                  />
                ) : (
                  <div style={{ width: "22px", height: "22px", borderRadius: "50%", border: "2px solid var(--border-strong)", flexShrink: 0 }} />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600", color: isAccountingRunning ? "var(--accent)" : "var(--text-primary)" }}>
                    4. Accounting & Tax Reasoning {isAccountingRunning && <span style={{ fontSize: "12px", fontWeight: "400" }}>(Classifying...)</span>}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    COA classification, TDS assessment, GST verification & GL balancing
                  </div>
                </div>
              </div>

              {/* Step 5: Final Finance Approval */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px", opacity: isApproved || isWaitingHitl2 ? 1 : 0.4 }}>
                {isApproved ? (
                  <CheckCircle2 size={22} color="#16a34a" style={{ flexShrink: 0 }} />
                ) : isWaitingHitl2 ? (
                  <div
                    style={{
                      width: "22px",
                      height: "22px",
                      borderRadius: "50%",
                      background: "#fef3c7",
                      color: "#b45309",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Clock size={15} />
                  </div>
                ) : (
                  <div style={{ width: "22px", height: "22px", borderRadius: "50%", border: "2px solid var(--border-strong)", flexShrink: 0 }} />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600", color: isWaitingHitl2 ? "#b45309" : isApproved ? "#16a34a" : "var(--text-primary)" }}>
                    5. Final Finance Approval (HITL #2) {isWaitingHitl2 && <span style={{ fontSize: "12px", fontWeight: "600" }}>(Awaiting Approval)</span>}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Final finance approval releases invoice to workspace
                  </div>
                </div>
              </div>
            </div>

            {/* Footer informational notice */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                fontSize: "13px",
                color: "var(--text-secondary)",
                padding: "10px",
              }}
            >
              <Sparkles size={16} color="var(--accent)" />
              <span>
                {isApproved
                  ? "Opening invoice workspace..."
                  : isWaitingHitl1 || isWaitingHitl2
                  ? "Invoice is awaiting internal finance review. It will become available as soon as approved."
                  : "Continuous automated pipeline active. Do not close this window."}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
