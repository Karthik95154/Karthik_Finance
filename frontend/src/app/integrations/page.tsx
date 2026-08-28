"use client";

import React, { useState, useEffect } from "react";
import AppShell from "@/components/AppShell";
import { Mail, User, ShieldAlert, CheckCircle2, AlertCircle, X, BookOpen } from "lucide-react";
import { getIMAPSettings, configureIMAPSettings, disconnectIMAP, IMAPSettings } from "@/lib/api";

export default function IntegrationsPage() {
  const [activeTab, setActiveTab] = useState<"email" | "profile">("email");
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Email Config State
  const [isEmailConnected, setIsEmailConnected] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [showGuideSidebar, setShowGuideSidebar] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [emailForm, setEmailForm] = useState({
    host: "imap.gmail.com",
    port: "993",
    email: "finance@company.com",
    password: "",
  });

  // Profile State
  const [profileForm, setProfileForm] = useState({
    fullName: "User Name",
    email: "user@company.com",
  });

  // Fetch IMAP config on load
  useEffect(() => {
    async function loadIMAPSettings() {
      try {
        const settings: IMAPSettings = await getIMAPSettings();
        if (settings.status === "connected" && settings.config) {
          setIsEmailConnected(true);
          setEmailForm({
            host: settings.config.imap_server || "imap.gmail.com",
            port: settings.config.imap_port || "993",
            email: settings.config.email_address || "",
            password: "",
          });
        }
      } catch (err: any) {
        console.warn("Failed to load IMAP settings:", err);
      }
    }
    loadIMAPSettings();
  }, []);

  // Clear notification after 4 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  const handleEmailSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailForm.host || !emailForm.port || !emailForm.email) {
      setNotification({ type: "error", message: "Host, Port, and Email are required." });
      return;
    }
    setIsConnecting(true);
    try {
      await configureIMAPSettings(emailForm);
      setIsEmailConnected(true);
      setShowEmailModal(false);
      setNotification({ type: "success", message: "Email connection established successfully!" });
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Failed to configure email connection." });
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnectEmail = async () => {
    try {
      await disconnectIMAP();
      setIsEmailConnected(false);
      setEmailForm((prev) => ({ ...prev, password: "" }));
      setNotification({ type: "success", message: "Email integration disconnected successfully." });
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Failed to disconnect integration." });
    }
  };

  const handleProfileSave = (e: React.FormEvent) => {
    e.preventDefault();
    setNotification({ type: "success", message: "Profile updated successfully!" });
  };

  return (
    <AppShell title="Integrations" subtitle="External Connections & Settings">
      <div style={{ maxWidth: "680px" }}>

        {/* Notification Banner */}
        {notification && (
          <div
            style={{
              marginBottom: "24px",
              padding: "14px 18px",
              borderRadius: "var(--radius-sm)",
              background: notification.type === "success" ? "#ecfdf5" : "#fef2f2",
              border: `1px solid ${notification.type === "success" ? "#a7f3d0" : "#fca5a5"}`,
              color: notification.type === "success" ? "#065f46" : "#991b1b",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              fontSize: "14px",
            }}
          >
            {notification.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
            <span>{notification.message}</span>
          </div>
        )}

        {/* Tabs Row */}
        <div style={{ display: "flex", borderBottom: "1px solid var(--border-subtle)", marginBottom: "28px", gap: "24px" }}>
          <button
            onClick={() => setActiveTab("email")}
            style={{
              paddingBottom: "12px",
              fontSize: "14px",
              fontWeight: "600",
              color: activeTab === "email" ? "var(--text-primary)" : "var(--text-secondary)",
              borderBottom: `2px solid ${activeTab === "email" ? "var(--accent)" : "transparent"}`,
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <Mail size={15} />
            Email Integration
          </button>
          <button
            onClick={() => setActiveTab("profile")}
            style={{
              paddingBottom: "12px",
              fontSize: "14px",
              fontWeight: "600",
              color: activeTab === "profile" ? "var(--text-primary)" : "var(--text-secondary)",
              borderBottom: `2px solid ${activeTab === "profile" ? "var(--accent)" : "transparent"}`,
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <User size={15} />
            User Profile
          </button>
        </div>

        {/* Tab Content */}
        <div
          style={{
            background: "#ffffff",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "28px",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          {activeTab === "email" ? (
            <div>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "24px" }}>
                <div>
                  <h3 style={{ fontSize: "17px", fontWeight: "600", marginBottom: "6px" }}>
                    Corporate Email Ingestion (IMAP)
                  </h3>
                  <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                    Connect your corporate inbox to auto-ingest incoming vendor invoices.
                  </p>
                </div>
                <span
                  style={{
                    padding: "4px 10px",
                    borderRadius: "12px",
                    fontSize: "12px",
                    fontWeight: "600",
                    background: isEmailConnected ? "#e6f4ea" : "var(--border-subtle)",
                    color: isEmailConnected ? "#137333" : "var(--text-secondary)",
                    flexShrink: 0,
                    marginLeft: "16px",
                  }}
                >
                  {isEmailConnected ? "● Connected" : "Inactive"}
                </span>
              </div>

              {/* Current Config Display */}
              <div
                style={{
                  background: "var(--bg-main)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-sm)",
                  padding: "20px",
                  fontSize: "13px",
                  marginBottom: "24px",
                }}
              >
                {isEmailConnected ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-secondary)" }}>IMAP Server</span>
                      <span style={{ fontWeight: "500" }}>{emailForm.host}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-secondary)" }}>Port</span>
                      <span style={{ fontWeight: "500" }}>{emailForm.port}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-secondary)" }}>Ingestion Email</span>
                      <span style={{ fontWeight: "500" }}>{emailForm.email}</span>
                    </div>
                  </div>
                ) : (
                  <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "10px 0" }}>
                    No email ingestion configured. Click Connect to set up.
                  </div>
                )}
              </div>

              <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                {isEmailConnected ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setShowEmailModal(true)}
                      className="btn btn-secondary"
                    >
                      Reconfigure
                    </button>
                    <button
                      type="button"
                      onClick={handleDisconnectEmail}
                      className="btn btn-secondary"
                      style={{ color: "#dc2626" }}
                    >
                      Disconnect
                    </button>
                  </>
                ) : (
                  <button type="button" onClick={() => setShowEmailModal(true)} className="btn btn-primary">
                    Connect Email
                  </button>
                )}
              </div>
            </div>
          ) : (
            <form onSubmit={handleProfileSave}>
              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "block", marginBottom: "8px", fontWeight: "500", fontSize: "13px" }}>
                  Full Name
                </label>
                <input
                  type="text"
                  className="form-input"
                  value={profileForm.fullName}
                  onChange={(e) => setProfileForm((p) => ({ ...p, fullName: e.target.value }))}
                  style={{ width: "100%", padding: "10px" }}
                  required
                />
              </div>
              <div style={{ marginBottom: "24px" }}>
                <label style={{ display: "block", marginBottom: "8px", fontWeight: "500", fontSize: "13px" }}>
                  Email Address
                </label>
                <input
                  type="email"
                  className="form-input"
                  value={profileForm.email}
                  onChange={(e) => setProfileForm((p) => ({ ...p, email: e.target.value }))}
                  style={{ width: "100%", padding: "10px" }}
                  required
                />
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button type="submit" className="btn btn-primary">Save Profile</button>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* IMAP Configuration Modal */}
      {showEmailModal && (
        <div
          style={{
            position: "fixed",
            top: 0, left: 0, right: 0, bottom: 0,
            background: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            backdropFilter: "blur(2px)",
            padding: "20px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "stretch",
              background: "#ffffff",
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1)",
              maxWidth: showGuideSidebar ? "900px" : "460px",
              width: "100%",
              transition: "max-width 0.25s ease-in-out",
              position: "relative",
            }}
          >
            {/* Form Panel */}
            <div style={{ flex: 1, padding: "28px", minWidth: "320px", position: "relative" }}>
              {/* Setup Guide toggle */}
              <button
                type="button"
                onClick={() => setShowGuideSidebar(!showGuideSidebar)}
                style={{
                  position: "absolute", top: "22px", left: "24px",
                  background: "#f5f5f7", border: "none", cursor: "pointer",
                  color: showGuideSidebar ? "var(--accent)" : "var(--text-secondary)",
                  display: "flex", alignItems: "center", gap: "6px",
                  fontSize: "12px", fontWeight: "600",
                  padding: "4px 8px", borderRadius: "4px",
                }}
              >
                <BookOpen size={14} /> Setup Guide
              </button>

              {/* Close */}
              <button
                type="button"
                onClick={() => setShowEmailModal(false)}
                style={{
                  position: "absolute", top: "22px", right: "24px",
                  background: "none", border: "none", cursor: "pointer",
                  color: "var(--text-secondary)",
                }}
              >
                <X size={20} />
              </button>

              <div style={{ marginTop: "36px", marginBottom: "20px" }}>
                <h3 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "4px" }}>
                  Configure Email Integration
                </h3>
                <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                  Enter your IMAP server connection details.
                </p>
              </div>

              <form onSubmit={handleEmailSave}>
                {[
                  { label: "IMAP Server Host", key: "host", type: "text", placeholder: "imap.gmail.com" },
                  { label: "IMAP Port", key: "port", type: "text", placeholder: "993" },
                  { label: "Email Address", key: "email", type: "email", placeholder: "finance@company.com" },
                ].map(({ label, key, type, placeholder }) => (
                  <div key={key} style={{ marginBottom: "14px" }}>
                    <label style={{ display: "block", marginBottom: "6px", fontSize: "13px", fontWeight: "500" }}>
                      {label}
                    </label>
                    <input
                      type={type}
                      className="form-input"
                      value={(emailForm as any)[key]}
                      onChange={(e) => setEmailForm((p) => ({ ...p, [key]: e.target.value }))}
                      placeholder={placeholder}
                      style={{ width: "100%", padding: "8px 12px" }}
                      required
                    />
                  </div>
                ))}

                <div style={{ marginBottom: "24px" }}>
                  <label style={{ display: "block", marginBottom: "6px", fontSize: "13px", fontWeight: "500" }}>
                    App Password
                  </label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder={isEmailConnected ? "••••••••••••••••" : "Enter 16-character app password"}
                    value={emailForm.password}
                    onChange={(e) => setEmailForm((p) => ({ ...p, password: e.target.value }))}
                    style={{ width: "100%", padding: "8px 12px" }}
                    required={!isEmailConnected}
                  />
                </div>

                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    onClick={() => setShowEmailModal(false)}
                    className="btn btn-secondary"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={isConnecting}>
                    {isConnecting ? "Connecting..." : "Save Connection"}
                  </button>
                </div>
              </form>
            </div>

            {/* Expandable Setup Guide */}
            {showGuideSidebar && (
              <div
                style={{
                  width: "400px",
                  borderLeft: "1px solid var(--border-subtle)",
                  backgroundColor: "#fafafa",
                  padding: "28px",
                  overflowY: "auto",
                  maxHeight: "520px",
                }}
              >
                <h4 style={{ fontSize: "15px", fontWeight: "700", marginBottom: "14px", display: "flex", alignItems: "center", gap: "8px" }}>
                  <BookOpen size={15} color="var(--accent)" />
                  Setup Guide (Gmail / M365)
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "14px", fontSize: "12.5px", lineHeight: "1.5" }}>
                  <div>
                    <div style={{ fontWeight: "600", marginBottom: "3px" }}>1. Enable IMAP Access</div>
                    <div style={{ color: "var(--text-secondary)" }}>
                      Turn on IMAP in Gmail Settings (Forwarding and POP/IMAP) or Office 365 dashboard.
                    </div>
                  </div>
                  <div>
                    <div style={{ fontWeight: "600", marginBottom: "3px" }}>2. Enable Two-Step Verification</div>
                    <div style={{ color: "var(--text-secondary)" }}>
                      Go to{" "}
                      <a href="https://myaccount.google.com/" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                        Google Settings
                      </a>{" "}
                      → Security → Turn on 2-Step Verification.
                    </div>
                  </div>
                  <div>
                    <div style={{ fontWeight: "600", marginBottom: "3px" }}>3. Generate an App Password</div>
                    <div style={{ color: "var(--text-secondary)" }}>
                      Go to{" "}
                      <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                        App Passwords
                      </a>
                      , select Mail, and click Create to get your 16-character code.
                    </div>
                  </div>
                  <div
                    style={{
                      background: "#fffbeb",
                      border: "1px solid #fef3c7",
                      color: "#b45309",
                      padding: "8px 10px",
                      borderRadius: "4px",
                      display: "flex",
                      gap: "6px",
                      fontSize: "11px",
                    }}
                  >
                    <ShieldAlert size={13} style={{ flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <strong>Warning:</strong> Never use your normal Gmail password. Only use the generated 16-character App Password.
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </AppShell>
  );
}
