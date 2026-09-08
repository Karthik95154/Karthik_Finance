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
    if (typeof window !== "undefined" && "Notification" in window) {
      if (Notification.permission === "default") {
        Notification.requestPermission();
      }
    }
  }, []);

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

        const isReadyForWorkspace =
          data.status === "HITL_REVIEW" ||
          data.status === "FINAL_HITL_REVIEW" ||
          data.status === "APPROVED" ||
          data.approval_status === "APPROVED" ||
          data.status === "COMPLETED" ||
          data.status === "PROCESSED";

        if (isReadyForWorkspace) {
          // Trigger Windows / Native Desktop Notification Toast
          if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
            const fileName = data.file_name || "Invoice";
            new Notification("Invoice Extraction Ready! ⚡", {
              body: `AI extraction completed for ${fileName}. Opening Invoice Workspace...`,
              icon: "/favicon.ico",
              tag: `invoice-ready-${invoiceId}`,
            });
          }

          // Extraction / processing ready -> redirect straight to workspace
          invalidateInvoicesCache();
          setTimeout(() => {
            router.push(`/finance/invoices/${invoiceId}`);
          }, 800);
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
  const isAccountingRunning = currentStatus === "PROCESSING_ACCOUNTING";

  // State 4: FINAL_HITL_REVIEW (Waiting for HITL Approval #2)
  const isWaitingHitl2 = currentStatus === "FINAL_HITL_REVIEW" || currentStatus === "PENDING_FINANCE_APPROVAL";

  // State 5: APPROVED (Completed or Ready)
  const isApproved =
    currentStatus === "APPROVED" ||
    approvalStatus === "APPROVED" ||
    currentStatus === "COMPLETED" ||
    currentStatus === "HITL_REVIEW" ||
    currentStatus === "FINAL_HITL_REVIEW";

  const isVlmDone = !isVlmRunning;
  const isAccountingDone = isApproved || currentStatus === "FINAL_HITL_REVIEW";

  const getHeaderTitle = () => {
    if (isApproved || isAccountingDone) return "Processing Complete!";
    if (isAccountingRunning) return "Classifying Accounting & Taxes...";
    if (isVlmRunning) return "Kimi K3 Extraction Active...";
    return "Processing Invoice";
  };

  const getHeaderSubtitle = () => {
    if (isApproved || isAccountingDone) return "AI extraction and tax reasoning finished. Redirecting to workspace...";
    if (isAccountingRunning) return "Classifying line items against Chart of Accounts (COA) and evaluating TDS rules.";
    if (isVlmRunning) return "Kimi K3 is extracting semantic tables, vendor details, header fields and line items.";
    return "Extracting and analyzing invoice details.";
  };

  return (
    <div className="container" style={{ maxWidth: "640px", paddingTop: "60px", paddingBottom: "80px" }}>
      <style>{`
        @keyframes pulseGlow {
          0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4); }
          70% { box-shadow: 0 0 0 12px rgba(37, 99, 235, 0); }
          100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
        }
        @keyframes shimmerLine {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>

      <div className="card" style={{ padding: "40px 32px", textAlign: "center", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02)", borderRadius: "16px" }}>
        {statusData?.status === "FAILED" || statusData?.accounting_status === "FAILED" ? (
          <div>
            <div
              style={{
                width: "60px",
                height: "60px",
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
            <h1 style={{ fontSize: "22px", fontWeight: "700", marginBottom: "8px" }}>Extraction Error</h1>
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
                width: "68px",
                height: "68px",
                borderRadius: "50%",
                background: isApproved || isAccountingDone ? "#f0fdf4" : "#eff6ff",
                color: isApproved || isAccountingDone ? "#16a34a" : "#2563eb",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 20px",
                animation: isApproved || isAccountingDone ? "none" : "pulseGlow 2s infinite",
                transition: "all 0.3s ease",
              }}
            >
              {isApproved || isAccountingDone ? (
                <CheckCircle2 size={40} color="#16a34a" />
              ) : (
                <Loader2 size={38} className="animate-spin" style={{ animation: "spin 1.2s linear infinite" }} />
              )}
            </div>

            <h1 style={{ fontSize: "24px", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "8px" }}>
              {getHeaderTitle()}
            </h1>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "24px", minHeight: "36px" }}>
              {getHeaderSubtitle()}
            </p>

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
                  marginBottom: "24px",
                  background: statusData.period_category === "PREVIOUS_FINANCIAL_YEAR" ? "#fef2f2" : "#f1f5f9",
                  color: statusData.period_category === "PREVIOUS_FINANCIAL_YEAR" ? "#b91c1c" : "#475569",
                  border: `1px solid ${statusData.period_category === "PREVIOUS_FINANCIAL_YEAR" ? "#fecaca" : "#e2e8f0"}`,
                }}
              >
                <Calendar size={13} />
                <span>{statusData.period_message}</span>
              </div>
            )}

            {statusData?.period_category === "PREVIOUS_FINANCIAL_YEAR" &&
              statusData?.period_decision === "PENDING" && (
                <div
                  style={{
                    background: "#fff1f2",
                    border: "1px solid #fecdd3",
                    borderRadius: "12px",
                    padding: "20px",
                    textAlign: "left",
                    marginBottom: "24px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", marginBottom: "16px" }}>
                    <div style={{ color: "#e11d48" }}><AlertTriangle size={24} /></div>
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: "700", color: "#9f1239" }}>Previous Financial Year</div>
                      <div style={{ fontSize: "13px", color: "#4c0519" }}>This invoice belongs to a previous financial year. Continue?</div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "12px" }}>
                    <button onClick={() => handlePeriodDecision("CANCEL")} style={{ padding: "8px 16px", borderRadius: "6px", background: "white", border: "1px solid #cbd5e1" }}>Cancel</button>
                    <button onClick={() => handlePeriodDecision("CONTINUE")} style={{ padding: "8px 16px", borderRadius: "6px", background: "#e11d48", color: "white" }}>Continue Processing</button>
                  </div>
                </div>
              )}

            <div
              style={{
                background: "linear-gradient(180deg, #f8fafc 0%, #ffffff 100%)",
                border: "1px solid #e2e8f0",
                borderRadius: "14px",
                padding: "24px",
                textAlign: "left",
                marginBottom: "24px",
                display: "flex",
                flexDirection: "column",
                gap: "24px",
                position: "relative",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: "16px", position: "relative", zIndex: 2 }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "#dcfce7", color: "#16a34a", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <CheckCircle2 size={18} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a" }}>1. Upload & Storage Completed</div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "flex-start", gap: "16px", position: "relative", zIndex: 2, opacity: isVlmDone || isVlmRunning ? 1 : 0.45 }}>
                {isVlmDone ? (
                  <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "#dcfce7", color: "#16a34a", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <CheckCircle2 size={18} />
                  </div>
                ) : isVlmRunning ? (
                  <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "#dbeafe", color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", animation: "pulseGlow 1.8s infinite", flexShrink: 0 }}>
                    <Loader2 size={16} className="animate-spin" />
                  </div>
                ) : (
                  <div style={{ width: "28px", height: "28px", borderRadius: "50%", border: "2px solid #cbd5e1", flexShrink: 0 }} />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "700", color: isVlmRunning ? "#2563eb" : "#0f172a", display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>2. Kimi K3 AI Extraction</span>
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "flex-start", gap: "16px", position: "relative", zIndex: 2, opacity: isAccountingDone || isAccountingRunning ? 1 : 0.45 }}>
                {isAccountingDone ? (
                  <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "#dcfce7", color: "#16a34a", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <CheckCircle2 size={18} />
                  </div>
                ) : isAccountingRunning ? (
                  <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "#dbeafe", color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", animation: "pulseGlow 1.8s infinite", flexShrink: 0 }}>
                    <Loader2 size={16} className="animate-spin" />
                  </div>
                ) : (
                  <div style={{ width: "28px", height: "28px", borderRadius: "50%", border: "2px solid #cbd5e1", flexShrink: 0 }} />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "700", color: isAccountingRunning ? "#2563eb" : "#0f172a", display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>3. Accounting & Tax Reasoning</span>
                  </div>
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", fontSize: "13px", color: "var(--text-secondary)", padding: "8px" }}>
              <Sparkles size={16} color="var(--accent)" />
              <span>{isApproved || isAccountingDone ? "Opening invoice workspace..." : "Automated AI pipeline active. Redirecting as soon as ready."}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
