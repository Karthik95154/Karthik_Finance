"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getInvoiceStatus, InvoiceStatus } from "@/lib/api";
import { CheckCircle2, Loader2, AlertCircle, ArrowLeft, Clock, Sparkles } from "lucide-react";

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

        if (data.status === "COMPLETED") {
          // Extraction & Accounting complete -> navigate to invoice view
          setTimeout(() => {
            router.push(`/finance/invoices/${invoiceId}`);
          }, 800);
        } else if (data.status === "FAILED" || data.accounting_status === "FAILED") {
          setError(data.error_message || "Invoice processing encountered an error.");
        } else {
          // Poll again in 3 seconds
          timer = setTimeout(checkStatus, 3000);
        }
      } catch (err: any) {
        if (!isMounted) return;
        console.warn("Status poll error:", err);
        timer = setTimeout(checkStatus, 4000);
      }
    }

    checkStatus();

    return () => {
      isMounted = false;
      if (timer) clearTimeout(timer);
    };
  }, [invoiceId, router]);

  const isVlmCompleted =
    statusData?.status === "PROCESSING_ACCOUNTING" || statusData?.status === "COMPLETED";
  const isAccountingRunning = statusData?.status === "PROCESSING_ACCOUNTING";
  const isCompleted = statusData?.status === "COMPLETED";

  return (
    <div className="container" style={{ maxWidth: "620px", paddingTop: "80px", paddingBottom: "100px" }}>
      <div className="card" style={{ padding: "40px 32px", textAlign: "center" }}>
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
              The AI model encountered an issue processing this document.
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
                background: "#f0f7ff",
                color: "var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 20px",
              }}
            >
              <Loader2 size={36} className="animate-spin" style={{ animation: "spin 1.5s linear infinite" }} />
            </div>

            <h1 style={{ fontSize: "24px", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "8px" }}>
              {isAccountingRunning
                ? "Reasoning Accounting & COA"
                : "Extracting Invoice Details"}
            </h1>
            <p style={{ fontSize: "15px", color: "var(--text-secondary)", marginBottom: "32px" }}>
              {isAccountingRunning
                ? "Qwen3-4B is classifying line items against Chart of Accounts and analyzing TDS rules."
                : "Qwen3-VL is extracting semantic tables, header fields & line items."}
            </p>

            {/* Progress Timeline */}
            <div
              style={{
                background: "var(--bg-main)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
                textAlign: "left",
                marginBottom: "24px",
                display: "flex",
                flexDirection: "column",
                gap: "16px",
              }}
            >
              {/* Step 1: Storage */}
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <CheckCircle2 size={20} color="var(--success)" />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600" }}>Invoice Saved to Supabase</div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Original binary securely stored in private bucket
                  </div>
                </div>
              </div>

              {/* Step 2: VLM Extraction */}
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                {isVlmCompleted ? (
                  <CheckCircle2 size={20} color="var(--success)" />
                ) : (
                  <div
                    style={{
                      width: "20px",
                      height: "20px",
                      borderRadius: "50%",
                      border: "2px solid var(--accent)",
                      borderTopColor: "transparent",
                      animation: "spin 1s linear infinite",
                    }}
                  />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600" }}>
                    Qwen3-VL Invoice Extraction
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Semantic tables, header fields & line items
                  </div>
                </div>
              </div>

              {/* Step 3: Accounting Reasoning */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  opacity: isVlmCompleted ? 1 : 0.4,
                }}
              >
                {isCompleted ? (
                  <CheckCircle2 size={20} color="var(--success)" />
                ) : isAccountingRunning ? (
                  <div
                    style={{
                      width: "20px",
                      height: "20px",
                      borderRadius: "50%",
                      border: "2px solid var(--accent)",
                      borderTopColor: "transparent",
                      animation: "spin 1s linear infinite",
                    }}
                  />
                ) : (
                  <CheckCircle2 size={20} color="var(--border-strong)" />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600" }}>
                    Qwen3-4B Accounting & Tax Reasoning
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    COA classification, confidence scoring & TDS analysis
                  </div>
                </div>
              </div>

              {/* Step 4: Complete */}
              <div style={{ display: "flex", alignItems: "center", gap: "12px", opacity: isCompleted ? 1 : 0.4 }}>
                <CheckCircle2 size={20} color={isCompleted ? "var(--success)" : "var(--border-strong)"} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "14px", fontWeight: "600" }}>Ready for Review</div>
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                    Final unified invoice workspace prepared
                  </div>
                </div>
              </div>
            </div>

            {/* Informational Message */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                fontSize: "13px",
                color: "var(--text-secondary)",
                padding: "12px",
                background: "#fdfdfd",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <Clock size={15} color="var(--text-tertiary)" />
              <span>Processing continues in the background. Long inference on Colab may take a few minutes.</span>
            </div>
          </div>
        )}
      </div>

      <style jsx global>{`
        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}
