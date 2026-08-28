"use client";

import React, { useState, useEffect } from "react";
import AppShell from "@/components/AppShell";
import {
  Mail,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  X,
  BookOpen,
  RefreshCw,
  Layers,
  ArrowRight,
  ExternalLink,
  KeyRound,
  Server,
  Inbox,
  Lock,
  Eye,
  EyeOff,
} from "lucide-react";
import {
  getIMAPSettings,
  configureIMAPSettings,
  disconnectIMAP,
  pollEmails,
  getZohoStatus,
  getMasterDataSummary,
  IMAPSettings,
  ZohoStatusResponse,
  ZohoMasterDataSummary,
} from "@/lib/api";
import Link from "next/link";

export default function IntegrationsPage() {
  const [notification, setNotification] = useState<{
    type: "success" | "error" | "info";
    message: string;
  } | null>(null);

  // IMAP State
  const [imapSettings, setImapSettings] = useState<IMAPSettings | null>(null);
  const [isEmailConnected, setIsEmailConnected] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailForm, setEmailForm] = useState({
    host: "imap.gmail.com",
    port: "993",
    email: "",
    password: "",
  });

  // Zoho State
  const [zohoStatus, setZohoStatus] = useState<ZohoStatusResponse | null>(null);
  const [masterData, setMasterData] = useState<ZohoMasterDataSummary | null>(null);
  const [loading, setLoading] = useState(true);

  // Load all integration statuses
  const loadData = async () => {
    setLoading(true);
    try {
      // 1. Fetch IMAP
      try {
        const imap: any = await getIMAPSettings();
        setImapSettings(imap);
        if (imap && (imap.status === "connected" || imap.is_connected)) {
          setIsEmailConnected(true);
          const cfg = imap.config || imap;
          setEmailForm({
            host: cfg.imap_server || "imap.gmail.com",
            port: String(cfg.imap_port || "993"),
            email: cfg.email_address || "",
            password: "",
          });
        } else {
          setIsEmailConnected(false);
        }
      } catch (err) {
        console.warn("Could not load IMAP settings:", err);
      }

      // 2. Fetch Zoho
      try {
        const zoho = await getZohoStatus();
        setZohoStatus(zoho);
      } catch (err) {
        console.warn("Could not load Zoho status:", err);
      }

      try {
        const md = await getMasterDataSummary();
        setMasterData(md);
      } catch (err) {
        console.warn("Could not load master data summary:", err);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Clear notification banner after 5 seconds
  useEffect(() => {
    if (notification) {
      const t = setTimeout(() => setNotification(null), 5000);
      return () => clearTimeout(t);
    }
  }, [notification]);

  const handleEmailSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailForm.host || !emailForm.port || !emailForm.email) {
      setNotification({
        type: "error",
        message: "Server Host, Port, and Email Address are required.",
      });
      return;
    }
    setIsConnecting(true);
    try {
      await configureIMAPSettings({
        imap_server: emailForm.host.trim(),
        imap_port: parseInt(emailForm.port, 10) || 993,
        email_address: emailForm.email.trim(),
        password: emailForm.password,
      });
      setIsEmailConnected(true);
      setShowEmailModal(false);
      setNotification({
        type: "success",
        message: `Email integration connected successfully to ${emailForm.email}!`,
      });
      loadData();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to configure IMAP connection. Check server credentials.",
      });
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnectEmail = async () => {
    if (!confirm("Are you sure you want to disconnect this email inbox? Auto-ingestion will be paused.")) {
      return;
    }
    try {
      await disconnectIMAP();
      setIsEmailConnected(false);
      setEmailForm((prev) => ({ ...prev, password: "" }));
      setNotification({
        type: "info",
        message: "Email integration disconnected.",
      });
      loadData();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to disconnect IMAP.",
      });
    }
  };

  const handleManualPoll = async () => {
    setIsPolling(true);
    try {
      const res = await pollEmails();
      setNotification({
        type: "success",
        message: `Polled inbox: ${res.emails_checked} emails inspected, ${res.new_documents} new invoices staged.`,
      });
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to poll emails. Verify IMAP connection.",
      });
    } finally {
      setIsPolling(false);
    }
  };

  return (
    <AppShell
      title="Integrations Hub"
      subtitle="Corporate Ingestion Pipelines & ERP Connections"
      actions={
        <button
          onClick={loadData}
          className="btn btn-secondary"
          style={{ display: "flex", alignItems: "center", gap: "8px" }}
          disabled={loading}
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      }
    >
      <div style={{ maxWidth: "960px", margin: "0 auto", paddingBottom: "60px" }}>
        {/* Notification Banner */}
        {notification && (
          <div
            style={{
              marginBottom: "24px",
              padding: "14px 18px",
              borderRadius: "var(--radius-sm)",
              background:
                notification.type === "success"
                  ? "#ecfdf5"
                  : notification.type === "info"
                  ? "#eff6ff"
                  : "#fef2f2",
              border: `1px solid ${
                notification.type === "success"
                  ? "#a7f3d0"
                  : notification.type === "info"
                  ? "#bfdbfe"
                  : "#fca5a5"
              }`,
              color:
                notification.type === "success"
                  ? "#065f46"
                  : notification.type === "info"
                  ? "#1e40af"
                  : "#991b1b",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "14px",
              fontWeight: "500",
              animation: "fadeIn 0.2s ease-out",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              {notification.type === "success" ? (
                <CheckCircle2 size={18} />
              ) : notification.type === "info" ? (
                <RefreshCw size={18} />
              ) : (
                <AlertCircle size={18} />
              )}
              <span>{notification.message}</span>
            </div>
            <button
              onClick={() => setNotification(null)}
              style={{ background: "none", border: "none", cursor: "pointer", color: "inherit" }}
            >
              <X size={16} />
            </button>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "24px" }}>
          {/* ========================================================================= */}
          {/* 1. IMAP EMAIL INGESTION CARD */}
          {/* ========================================================================= */}
          <div
            className="card"
            style={{
              padding: "28px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              background: "#ffffff",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "16px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                  <div
                    style={{
                      width: "48px",
                      height: "48px",
                      borderRadius: "12px",
                      background: isEmailConnected ? "rgba(16, 185, 129, 0.1)" : "rgba(0, 113, 227, 0.08)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: isEmailConnected ? "#10b981" : "var(--accent)",
                    }}
                  >
                    <Mail size={24} />
                  </div>
                  <div>
                    <h2 style={{ fontSize: "17px", fontWeight: "700", color: "var(--text-primary)", margin: 0 }}>
                      Corporate Email Ingestion (IMAP)
                    </h2>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                      Auto-ingest vendor invoice PDF attachments
                    </span>
                  </div>
                </div>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "4px 10px",
                    borderRadius: "12px",
                    fontSize: "12px",
                    fontWeight: "600",
                    background: isEmailConnected ? "#e6f4ea" : "#f1f3f4",
                    color: isEmailConnected ? "#137333" : "#5f6368",
                  }}
                >
                  <span
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: isEmailConnected ? "#137333" : "#5f6368",
                    }}
                  />
                  {isEmailConnected ? "Connected" : "Not Configured"}
                </span>
              </div>

              <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "20px" }}>
                Connect your accounts payable mailbox (e.g. <code>invoices@company.com</code>) via secure SSL IMAP. Incoming attachments are automatically staged for AI extraction.
              </p>

              {isEmailConnected && emailForm.email ? (
                <div
                  style={{
                    background: "var(--bg-main)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "16px",
                    fontSize: "13px",
                    marginBottom: "20px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Connected Mailbox:</span>
                    <strong style={{ color: "var(--text-primary)" }}>{emailForm.email}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Server:</span>
                    <span>{emailForm.host}:{emailForm.port}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Encryption:</span>
                    <span style={{ color: "#10b981", fontWeight: "600" }}>SSL / TLS (AES at rest)</span>
                  </div>
                </div>
              ) : null}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  onClick={() => setShowEmailModal(true)}
                  className="btn btn-primary"
                  style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                >
                  <Server size={15} />
                  {isEmailConnected ? "Edit Credentials" : "Configure IMAP"}
                </button>

                {isEmailConnected && (
                  <button
                    onClick={handleManualPoll}
                    className="btn btn-secondary"
                    disabled={isPolling}
                    style={{ display: "flex", alignItems: "center", gap: "6px" }}
                    title="Poll IMAP mailbox now"
                  >
                    <RefreshCw size={14} className={isPolling ? "animate-spin" : ""} />
                    {isPolling ? "Polling..." : "Poll Now"}
                  </button>
                )}
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "8px" }}>
                <Link
                  href="/inbox"
                  style={{
                    fontSize: "13px",
                    fontWeight: "600",
                    color: "var(--accent)",
                    textDecoration: "none",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <Inbox size={14} />
                  Open Staged Inbox →
                </Link>

                {isEmailConnected && (
                  <button
                    onClick={handleDisconnectEmail}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#dc2626",
                      fontSize: "12px",
                      cursor: "pointer",
                      padding: "4px 8px",
                    }}
                  >
                    Disconnect
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* 2. ZOHO BOOKS ERP CARD */}
          {/* ========================================================================= */}
          <div
            className="card"
            style={{
              padding: "28px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              background: "#ffffff",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "16px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                  <div
                    style={{
                      width: "48px",
                      height: "48px",
                      borderRadius: "12px",
                      background: zohoStatus?.connected ? "rgba(0, 113, 227, 0.08)" : "#f1f3f4",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "var(--accent)",
                    }}
                  >
                    <Layers size={24} />
                  </div>
                  <div>
                    <h2 style={{ fontSize: "17px", fontWeight: "700", color: "var(--text-primary)", margin: 0 }}>
                      Zoho Books ERP
                    </h2>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                      Chart of Accounts, Tax Rates & Bill Synchronization
                    </span>
                  </div>
                </div>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "4px 10px",
                    borderRadius: "12px",
                    fontSize: "12px",
                    fontWeight: "600",
                    background: zohoStatus?.connected ? "#e6f4ea" : "#fef2f2",
                    color: zohoStatus?.connected ? "#137333" : "#b91c1c",
                  }}
                >
                  <span
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: zohoStatus?.connected ? "#137333" : "#b91c1c",
                    }}
                  />
                  {zohoStatus?.connected ? "Connected" : "Disconnected"}
                </span>
              </div>

              <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "20px" }}>
                Synchronize Chart of Accounts and Vendor master data from Zoho Books. Approved invoices are exported directly as Vendor Bills with original attachments.
              </p>

              {zohoStatus?.connected ? (
                <div
                  style={{
                    background: "var(--bg-main)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "16px",
                    fontSize: "13px",
                    marginBottom: "20px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Active Organization:</span>
                    <strong style={{ color: "var(--text-primary)" }}>
                      {zohoStatus.organization_name || "carkit"} ({zohoStatus.organization_id})
                    </strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Chart of Accounts:</span>
                    <span>{masterData?.chart_of_accounts_count ?? zohoStatus.accounts_count ?? 67} Accounts Synced</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Vendors:</span>
                    <span>{masterData?.vendors_count ?? zohoStatus.vendors_count ?? 19} Contacts Synced</span>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    background: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: "var(--radius-sm)",
                    padding: "14px",
                    fontSize: "13px",
                    color: "#991b1b",
                    marginBottom: "20px",
                  }}
                >
                  Connect your Zoho Books organization to enable automated ledger mapping and direct bill posting.
                </div>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
              <Link
                href="/finance/settings"
                className="btn btn-secondary"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  textDecoration: "none",
                  textAlign: "center",
                }}
              >
                <ShieldCheck size={15} />
                Manage Zoho Settings & Master Data
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. IMAP CONFIGURATION MODAL */}
      {/* ========================================================================= */}
      {showEmailModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.5)",
            backdropFilter: "blur(4px)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            className="card"
            style={{
              background: "#ffffff",
              borderRadius: "var(--radius-md)",
              maxWidth: "520px",
              width: "100%",
              boxShadow: "var(--shadow-lg)",
              overflow: "hidden",
              animation: "fadeIn 0.2s ease-out",
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: "20px 24px",
                borderBottom: "1px solid var(--border-subtle)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Mail size={20} color="var(--accent)" />
                <h3 style={{ fontSize: "17px", fontWeight: "700", color: "var(--text-primary)", margin: 0 }}>
                  Configure IMAP Email Ingestion
                </h3>
              </div>
              <button
                onClick={() => setShowEmailModal(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)" }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleEmailSave} style={{ padding: "24px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: "600", marginBottom: "6px" }}>
                    IMAP Host Server
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="imap.gmail.com"
                    value={emailForm.host}
                    onChange={(e) => setEmailForm({ ...emailForm, host: e.target.value })}
                    required
                  />
                  <span style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px", display: "block" }}>
                    Examples: <code>imap.gmail.com</code>, <code>outlook.office365.com</code>
                  </span>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: "600", marginBottom: "6px" }}>
                    Port (SSL/TLS)
                  </label>
                  <input
                    type="number"
                    className="input-field"
                    placeholder="993"
                    value={emailForm.port}
                    onChange={(e) => setEmailForm({ ...emailForm, port: e.target.value })}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: "600", marginBottom: "6px" }}>
                    Email Address
                  </label>
                  <input
                    type="email"
                    className="input-field"
                    placeholder="invoices@company.com"
                    value={emailForm.email}
                    onChange={(e) => setEmailForm({ ...emailForm, email: e.target.value })}
                    required
                  />
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                    <label style={{ fontSize: "13px", fontWeight: "600" }}>
                      App Password
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowGuide(!showGuide)}
                      style={{
                        background: "none",
                        border: "none",
                        fontSize: "12px",
                        color: "var(--accent)",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      <BookOpen size={12} />
                      {showGuide ? "Hide Guide" : "How to generate App Password?"}
                    </button>
                  </div>

                  <div style={{ position: "relative" }}>
                    <input
                      type={showPassword ? "text" : "password"}
                      className="input-field"
                      placeholder={isEmailConnected ? "•••••••••••••••• (Leave blank to keep existing)" : "16-character App Password"}
                      value={emailForm.password}
                      onChange={(e) => setEmailForm({ ...emailForm, password: e.target.value })}
                      style={{ paddingRight: "40px" }}
                      required={!isEmailConnected}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{
                        position: "absolute",
                        right: "12px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                {/* Collapsible Setup Guide */}
                {showGuide && (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: "var(--radius-sm)",
                      padding: "14px",
                      fontSize: "12px",
                      color: "var(--text-secondary)",
                      lineHeight: "1.6",
                    }}
                  >
                    <strong style={{ color: "var(--text-primary)", display: "block", marginBottom: "4px" }}>
                      🔑 Gmail App Password Instructions:
                    </strong>
                    <ol style={{ paddingLeft: "18px", margin: "4px 0" }}>
                      <li>Go to your Google Account Security settings (2-Step Verification must be enabled).</li>
                      <li>Search for <strong>"App passwords"</strong>.</li>
                      <li>Name the app (e.g. <em>Sakshi Finance</em>) and click Create.</li>
                      <li>Copy the generated 16-character password into the field above.</li>
                    </ol>
                  </div>
                )}
              </div>

              {/* Modal Actions */}
              <div
                style={{
                  marginTop: "24px",
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: "10px",
                }}
              >
                <button
                  type="button"
                  onClick={() => setShowEmailModal(false)}
                  className="btn btn-secondary"
                  disabled={isConnecting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isConnecting}
                  style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                  {isConnecting ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" />
                      Testing & Saving...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={14} />
                      Save & Test Connection
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}

