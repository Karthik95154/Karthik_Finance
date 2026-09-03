"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Server,
  Database,
  Cloud,
  Cpu,
  Brain,
  Globe,
  ExternalLink,
  Activity,
  Zap,
  Info,
  X,
} from "lucide-react";
import { HealthResponse, ServiceHealthDetail } from "@/lib/api";

interface SystemStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  health: HealthResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export function getStatusBadge(status?: string, code?: number | null) {
  const s = (status || "").toLowerCase();
  if (code === 200 || s === "online" || s === "connected" || s === "ok" || s === "healthy") {
    return {
      bg: "#ecfdf5",
      border: "#a7f3d0",
      text: "#065f46",
      dot: "#10b981",
      label: code ? `200 OK (Online)` : "Online",
      icon: CheckCircle2,
    };
  }
  if (code === 404 || s.includes("404") || s.includes("not found")) {
    return {
      bg: "#fff1f2",
      border: "#fecdd3",
      text: "#9f1239",
      dot: "#f43f5e",
      label: "404 Not Found",
      icon: AlertTriangle,
    };
  }
  if (code && code >= 500) {
    return {
      bg: "#fef2f2",
      border: "#fecaca",
      text: "#991b1b",
      dot: "#ef4444",
      label: `HTTP ${code} Error`,
      icon: XCircle,
    };
  }
  if (s === "offline" || s === "disconnected" || s.includes("unreachable") || s.includes("refused")) {
    return {
      bg: "#f3f4f6",
      border: "#e5e7eb",
      text: "#4b5563",
      dot: "#9ca3af",
      label: "Offline",
      icon: XCircle,
    };
  }
  if (s === "timeout") {
    return {
      bg: "#fffbeb",
      border: "#fde68a",
      text: "#92400e",
      dot: "#f59e0b",
      label: "Timeout (>4s)",
      icon: AlertTriangle,
    };
  }
  if (s === "degraded") {
    return {
      bg: "#fffbeb",
      border: "#fde68a",
      text: "#92400e",
      dot: "#f59e0b",
      label: "Degraded",
      icon: AlertTriangle,
    };
  }
  return {
    bg: "#f3f4f6",
    border: "#e5e7eb",
    text: "#4b5563",
    dot: "#9ca3af",
    label: status || "Checking...",
    icon: Activity,
  };
}

export default function SystemStatusModal({
  isOpen,
  onClose,
  health,
  loading,
  onRefresh,
}: SystemStatusModalProps) {
  if (!isOpen) return null;

  const services = health?.services || {};
  const vlm = services["colab_vlm"] || {
    name: "Qwen3-VL Vision Engine",
    status: health?.colab_vlm?.includes("404") ? "404_error" : health?.colab_vlm || "offline",
    message: health?.colab_vlm || "Status pending",
  };
  const acc = services["colab_accounting"] || {
    name: "Qwen3-4B Accounting Engine",
    status: health?.colab_accounting?.includes("404") ? "404_error" : health?.colab_accounting || "offline",
    message: health?.colab_accounting || "Status pending",
  };
  const db = services["database"] || {
    name: "PostgreSQL Database",
    status: health?.database || "error",
    message: health?.database || "Database",
  };
  const storage = services["storage"] || {
    name: "Supabase File Storage",
    status: health?.storage || "error",
    message: health?.storage || "Storage",
  };
  const backend = services["backend"] || {
    name: "FastAPI Finance Core",
    status: health ? "online" : "offline",
    status_code: health ? 200 : null,
    message: health ? "200 OK - Core Engine Running" : "Backend unreachable",
    latency_ms: 0.5,
  };

  const serviceList = [
    {
      key: "backend",
      icon: Server,
      detail: {
        ...backend,
        name: "Finance Core Application",
      },
      desc: "Handles invoice workflows, accounting rules, user reviews, and audit tracking.",
    },
    {
      key: "db",
      icon: Database,
      detail: {
        ...db,
        name: "Accounting Database",
      },
      desc: "Stores invoice records, Chart of Accounts, tax configurations, and balanced journal entries.",
    },
    {
      key: "storage",
      icon: Cloud,
      detail: {
        ...storage,
        name: "Invoice Document Vault",
      },
      desc: "Secure storage for all uploaded invoice PDFs, receipt scans, and source documents.",
    },
    {
      key: "vlm",
      icon: Cpu,
      detail: {
        ...vlm,
        name: "AI Invoice Reader (Vision Model)",
      },
      desc: "Extracts vendor names, invoice numbers, line items, and taxes from uploaded documents.",
    },
    {
      key: "accounting",
      icon: Brain,
      detail: {
        ...acc,
        name: "AI Tax & Accounting Advisor",
      },
      desc: "Recommends account classifications, evaluates GST Place of Supply, and assesses TDS withholding.",
    },
  ];

  const overallBadge = getStatusBadge(
    health?.status === "ok" ? "online" : health?.status === "degraded" ? "degraded" : "offline",
    health?.status === "ok" ? 200 : undefined
  );

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(15, 23, 42, 0.65)",
        backdropFilter: "blur(6px)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "640px",
          backgroundColor: "#ffffff",
          borderRadius: "14px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          border: "1px solid #e2e8f0",
          overflow: "hidden",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: "20px 24px 16px",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#fafafa",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "10px",
                background: "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                boxShadow: "0 2px 8px rgba(0, 113, 227, 0.25)",
              }}
            >
              <Activity size={20} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: "17px",
                  fontWeight: "700",
                  color: "#0f172a",
                  lineHeight: "1.2",
                  margin: 0,
                }}
              >
                Application & Service Status
              </h2>
              <p
                style={{
                  fontSize: "12px",
                  color: "#64748b",
                  margin: "2px 0 0",
                }}
              >
                Live status of your invoice processing, AI extraction, and accounting services
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="btn btn-secondary"
              style={{
                padding: "6px 12px",
                fontSize: "12px",
                fontWeight: "600",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                borderRadius: "6px",
              }}
            >
              <RefreshCw
                size={14}
                className={loading ? "spin-icon" : ""}
                style={{ animation: loading ? "spin 1s linear infinite" : "none" }}
              />
              <span>{loading ? "Checking..." : "Refresh"}</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "#94a3b8",
                padding: "6px",
                borderRadius: "6px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div style={{ padding: "20px 24px", overflowY: "auto", flex: 1 }}>
          {/* Overall Health Summary Banner */}
          <div
            style={{
              padding: "12px 16px",
              borderRadius: "8px",
              background: overallBadge.bg,
              border: `1px solid ${overallBadge.border}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "20px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor: overallBadge.dot,
                  boxShadow: `0 0 0 3px ${overallBadge.border}`,
                }}
              />
              <div>
                <div style={{ fontSize: "13px", fontWeight: "700", color: overallBadge.text }}>
                  Overall Status: {health?.status === "ok" ? "All Systems Operational" : health?.status === "degraded" ? "Degraded (Some Endpoints Offline/404)" : "System Degraded or Offline"}
                </div>
                <div style={{ fontSize: "11px", color: overallBadge.text, opacity: 0.85 }}>
                  Last Checked: {health?.timestamp ? new Date(health.timestamp).toLocaleTimeString() : "Just now"}
                </div>
              </div>
            </div>
            <span
              style={{
                fontSize: "11px",
                fontWeight: "700",
                padding: "3px 8px",
                borderRadius: "4px",
                background: "#ffffff",
                color: overallBadge.text,
                border: `1px solid ${overallBadge.border}`,
              }}
            >
              {overallBadge.label}
            </span>
          </div>

          {/* Service Cards Grid */}
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {serviceList.map((svc) => {
              const Icon = svc.icon;
              const badge = getStatusBadge(svc.detail.status, svc.detail.status_code);
              const BadgeIcon = badge.icon;
              return (
                <div
                  key={svc.key}
                  style={{
                    padding: "14px 16px",
                    borderRadius: "10px",
                    border: "1px solid #e2e8f0",
                    background: "#ffffff",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    transition: "border-color 0.15s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <div
                        style={{
                          width: "30px",
                          height: "30px",
                          borderRadius: "6px",
                          background: "#f1f5f9",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "#334155",
                        }}
                      >
                        <Icon size={16} />
                      </div>
                      <div>
                        <div style={{ fontSize: "13px", fontWeight: "700", color: "#0f172a" }}>
                          {svc.detail.name}
                        </div>
                        {svc.detail.endpoint && (
                          <div
                            style={{
                              fontSize: "11px",
                              color: "#64748b",
                              fontFamily: "monospace",
                              maxWidth: "320px",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                            title={svc.detail.endpoint}
                          >
                            {svc.detail.endpoint}
                          </div>
                        )}
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      {svc.detail.latency_ms !== null && svc.detail.latency_ms !== undefined && (
                        <span
                          style={{
                            fontSize: "11px",
                            fontFamily: "monospace",
                            color: "#64748b",
                            background: "#f8fafc",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            border: "1px solid #e2e8f0",
                          }}
                        >
                          {svc.detail.latency_ms}ms
                        </span>
                      )}
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: "600",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          background: badge.bg,
                          color: badge.text,
                          border: `1px solid ${badge.border}`,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <BadgeIcon size={12} />
                        <span>{badge.label}</span>
                      </span>
                    </div>
                  </div>

                  <div style={{ fontSize: "12px", color: "#475569", lineHeight: "1.4" }}>
                    {svc.desc}
                  </div>

                  {/* Error / 404 User Helper */}
                  {(svc.detail.status_code === 404 || svc.detail.status === "404_error" || svc.detail.status === "offline") && (
                    <div
                      style={{
                        padding: "8px 12px",
                        borderRadius: "6px",
                        background: "#fff1f2",
                        border: "1px solid #fecdd3",
                        fontSize: "12px",
                        color: "#9f1239",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "8px",
                      }}
                    >
                      <Info size={15} style={{ flexShrink: 0, marginTop: "1px" }} />
                      <div>
                        {svc.detail.status_code === 404 || svc.detail.status === "404_error" ? (
                          <span>
                            <strong>AI Service Unavailable (404):</strong> The AI automated extraction is temporarily offline. You can still upload, view, edit, and export invoices manually.
                          </span>
                        ) : (
                          <span>
                            <strong>Service Offline:</strong> Cannot reach this service. Please verify your internet connection or check back in a few moments.
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid #e2e8f0",
            background: "#f8fafc",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ fontSize: "12px", color: "#64748b" }}>
            All systems auto-check every 30 seconds.
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-primary"
            style={{
              padding: "7px 18px",
              fontSize: "13px",
              fontWeight: "600",
              borderRadius: "6px",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
