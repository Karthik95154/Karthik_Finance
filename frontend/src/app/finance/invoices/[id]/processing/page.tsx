"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getInvoiceStatus, InvoiceStatus } from "@/lib/api";
import { CheckCircle2, Loader2, AlertCircle, ArrowLeft, ArrowRight, Sparkles, FileText, Database, Layers, Send } from "lucide-react";

export default function InvoiceProcessingPage() {
  const params = useParams();
  const router = useRouter();
  const invoiceId = params?.id as string;

  const [statusData, setStatusData] = useState<InvoiceStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollCount, setPollCount] = useState(0);

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

        const isFinished =
          data.status === "COMPLETED" ||
          data.status === "APPROVED" ||
          data.status === "FINAL_HITL_REVIEW" ||
          data.accounting_status === "COMPLETED" ||
          data.accounting_status === "SUCCESS";

        if (isFinished) {
          // All models (VLM, COA, TDS, GST/ITC, Financial Validation, Journal) complete -> navigate to invoice workspace
          setTimeout(() => {
            router.push(`/finance/invoices/${invoiceId}`);
          }, 800);
        } else if (data.status === "FAILED" || data.accounting_status === "FAILED") {
          setError(data.error_message || "Invoice processing encountered an issue.");
        } else {
          // Continuously poll every 2.0s across all stages (VLM -> COA -> Final Generation)
          timer = setTimeout(checkStatus, 2000);
        }
      } catch (err: any) {
        if (!isMounted) return;
        console.warn("Status poll error:", err);
        timer = setTimeout(checkStatus, 2500);
      }
    }

    checkStatus();

    return () => {
      isMounted = false;
      if (timer) clearTimeout(timer);
    };
  }, [invoiceId, router]);

  const currentStatus = statusData?.status || "PROCESSING_VLM";

  // Step 1: Upload (Always complete upon hitting this screen)
  const isUploadDone = true;

  // Step 2: Qwen-VL Model
  const isVlmRunning = currentStatus === "UPLOADED" || currentStatus === "PROCESSING_VLM";
  const isVlmDone =
    currentStatus === "PROCESSING_ACCOUNTING" ||
    currentStatus === "ACCOUNTING_PROCESSING" ||
    currentStatus === "FINAL_HITL_REVIEW" ||
    currentStatus === "COMPLETED" ||
    currentStatus === "APPROVED";

  // Step 3: COA & Accounting Reasoning
  const isCoaRunning =
    currentStatus === "PROCESSING_ACCOUNTING" ||
    currentStatus === "ACCOUNTING_PROCESSING";
  const isCoaDone =
    currentStatus === "FINAL_HITL_REVIEW" ||
    currentStatus === "COMPLETED" ||
    currentStatus === "APPROVED";

  // Step 4: Final Generation (GST verification & Double-Entry Journal)
  const isFinalRunning = isCoaDone && currentStatus !== "COMPLETED" && currentStatus !== "APPROVED";
  const isFinalDone =
    currentStatus === "COMPLETED" ||
    currentStatus === "APPROVED" ||
    currentStatus === "FINAL_HITL_REVIEW";

  // Step 5: Complete & Ready
  const isAllComplete =
    currentStatus === "COMPLETED" ||
    currentStatus === "APPROVED" ||
    currentStatus === "FINAL_HITL_REVIEW" ||
    statusData?.accounting_status === "COMPLETED" ||
    statusData?.accounting_status === "SUCCESS";

  // Dynamic header text based on active step
  const getHeaderTitle = () => {
    if (isAllComplete) return "Processing Complete!";
    if (isFinalRunning) return "Generating Final Journal & Taxes";
    if (isCoaRunning) return "COA Classification & TDS Analysis";
    if (isVlmRunning) return "Qwen3-VL Model Running";
    return "Processing Invoice";
  };

  const getHeaderSubtitle = () => {
    if (isAllComplete) return "All fields extracted, verified & reconciled. Redirecting to invoice workspace...";
    if (isFinalRunning) return "Computing deterministic GST tax reconciliation and balancing double-entry journal entries.";
    if (isCoaRunning) return "Classifying line items against Chart of Accounts (COA) and evaluating TDS rules.";
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
                background: isAllComplete ? "#f0fdf4" : "#f0f7ff",
                color: isAllComplete ? "var(--success)" : "var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 20px",
                transition: "all 0.3s ease",
              }}
            >
              {isAllComplete ? (
                <CheckCircle2 size={36} color="#16a34a" />
              ) : (
                <Loader2 size={36} className="animate-spin" style={{ animation: "spin 1.5s linear infinite" }} />
              )}
            </div>

            <h1 style={{ fontSize: "24px", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "8px" }}>
              {getHeaderTitle()}
            </h1>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "32px", minHeight: "42px" }}>
              {getHeaderSubtitle()}
            </p>

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

              {/* Step 2: Qwen3-VL Model Running */}
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
                    Extracting vendor details, line items & amounts
                  </div>
                </div>
              </div>

              {/* Step 3: COA & Accounting Reasoning */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px", opacity: isCoaDone || isCoaRunning ? 1 : 0.4 }}>
                {isCoaDone ? (
                  <CheckCircle2 size={22} color="#16a34a" style={{ flexShrink: 0 }} />
                ) : isCoaRunning ? (
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
                  <div style={{ fontSize: "14px", fontWeight: "600", color: isCoaRunning ? "var(--accent)" : "var(--text-primary)" }}>
                    3. COA & Accounting Reasoning {isCoaRunning && <span style={{ fontSize: "12px", fontWeight: "400" }}>(Classifying...)</span>}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Chart of Accounts mapping, TDS rules & GST analysis
                  </div>
                </div>
              </div>

              {/* Step 4: Final Generation */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px", opacity: isFinalDone || isFinalRunning ? 1 : 0.4 }}>
                {isFinalDone ? (
                  <CheckCircle2 size={22} color="#16a34a" style={{ flexShrink: 0 }} />
                ) : isFinalRunning ? (
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
                  <div style={{ fontSize: "14px", fontWeight: "600", color: isFinalRunning ? "var(--accent)" : "var(--text-primary)" }}>
                    4. Final Generation & Journal Balancing {isFinalRunning && <span style={{ fontSize: "12px", fontWeight: "400" }}>(Generating...)</span>}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Deterministic GST verification & double-entry journal creation
                  </div>
                </div>
              </div>

              {/* Step 5: Complete & Review */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px", opacity: isAllComplete ? 1 : 0.4 }}>
                <CheckCircle2 size={22} color={isAllComplete ? "#16a34a" : "var(--border-strong)"} style={{ flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600", color: isAllComplete ? "#16a34a" : "var(--text-primary)" }}>
                    5. Complete — Invoice Workspace Ready
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Review extracted fields, edit data & sync to Zoho Books
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
                {isAllComplete
                  ? "Processing finished! Opening invoice workspace..."
                  : "Continuous automated pipeline active. Do not close this window."}
              </span>
            </div>

            {isAllComplete && (
              <button
                onClick={() => router.push(`/finance/invoices/${invoiceId}`)}
                className="btn btn-primary"
                style={{ width: "100%", marginTop: "14px", padding: "12px", justifyContent: "center" }}
              >
                <span>Go to Invoice Workspace</span>
                <ArrowRight size={16} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
