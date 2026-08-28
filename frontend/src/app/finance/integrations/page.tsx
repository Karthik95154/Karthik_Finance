"use client";

import React, { useState, useEffect } from "react";
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
            port: String(settings.config.imap_port || "993"),
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
      setNotification({
        type: "error",
        message: "Failed to connect. Host, Port, and Email are required.",
      });
      return;
    }
    setIsConnecting(true);
    try {
      await configureIMAPSettings({
        imap_server: emailForm.host,
        imap_port: parseInt(emailForm.port, 10) || 993,
        email_address: emailForm.email,
        password: emailForm.password,
      });
      setIsEmailConnected(true);
      setShowEmailModal(false);
      setNotification({
        type: "success",
        message: "Email connection established successfully!",
      });
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to configure email connection.",
      });
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnectEmail = async () => {
    try {
      await disconnectIMAP();
      setIsEmailConnected(false);
      setEmailForm((prev) => ({ ...prev, password: "" }));
      setNotification({
        type: "success",
        message: "Email integration disconnected successfully.",
      });
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to disconnect integration.",
      });
    }
  };

  const handleProfileSave = (e: React.FormEvent) => {
    e.preventDefault();
    setNotification({
      type: "success",
      message: "Profile updated successfully!",
    });
  };

  return (
    <div className="container" style={{ maxWidth: "680px", paddingTop: "60px", paddingBottom: "80px" }}>

      {/* Page Header */}
      <div style={{ textAlign: "center", marginBottom: "36px" }}>
        <h1 style={{ fontSize: "32px", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "10px" }}>
          Integrations & Settings
        </h1>
        <p style={{ fontSize: "16px", color: "var(--text-secondary)" }}>
          Manage corporate ingestion pipelines and account settings.
        </p>
      </div>

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
            animation: "fadeIn 0.2s ease-out",
          }}
        >
          {notification.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{notification.message}</span>
        </div>
      )}

      {/* Tabs Row */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-subtle)",
          marginBottom: "28px",
          gap: "24px",
        }}
      >
        <button
          onClick={() => setActiveTab("email")}
          style={{
            paddingBottom: "12px",
            fontSize: "15px",
            fontWeight: "600",
            color: activeTab === "email" ? "var(--text-primary)" : "var(--text-secondary)",
            borderBottom: `2px solid ${activeTab === "email" ? "var(--text-primary)" : "transparent"}`,
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
            transition: "all 0.15s ease",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <Mail size={16} />
          Email Integration
        </button>
        <button
          onClick={() => setActiveTab("profile")}
          style={{
            paddingBottom: "12px",
            fontSize: "15px",
            fontWeight: "600",
            color: activeTab === "profile" ? "var(--text-primary)" : "var(--text-secondary)",
            borderBottom: `2px solid ${activeTab === "profile" ? "var(--text-primary)" : "transparent"}`,
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
            transition: "all 0.15s ease",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <User size={16} />
          User Profile
        </button>
      </div>

      {/* Tab Contents */}
      <div className="card" style={{ padding: "32px" }}>
        {activeTab === "email" ? (
          <div>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "24px" }}>
              <div>
                <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "6px" }}>
                  ✉️ Corporate Email Ingestion (IMAP)
                </h3>
                <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
                  Connect your corporate inbox to auto-ingest incoming vendor invoices.
                </p>
              </div>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: "12px",
                  fontSize: "12px",
                  fontWeight: "600",
                  background: isEmailConnected ? "#e6f4ea" : "#f1f3f4",
                  color: isEmailConnected ? "#137333" : "#5f6368",
                }}
              >
                {isEmailConnected ? "Connected" : "Inactive"}
              </span>
            </div>

            <div
              style={{
                background: "var(--bg-main)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)",
                padding: "20px",
                fontSize: "14px",
                marginBottom: "24px",
              }}
            >
              {isEmailConnected ? (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ color: "var(--text-secondary)" }}>IMAP Server:</span>
                    <span style={{ fontWeight: "500" }}>{emailForm.host}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Port:</span>
                    <span style={{ fontWeight: "500" }}>{emailForm.port}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Ingestion Email:</span>
                    <span style={{ fontWeight: "500" }}>{emailForm.email}</span>
                  </div>
                </div>
              ) : (
                <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "10px 0" }}>
                  No email ingestion configured. Click Connect below to set up.
                </div>
              )}
            </div>

            <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
              {isEmailConnected ? (
                <button type="button" onClick={handleDisconnectEmail} className="btn btn-secondary" style={{ color: "var(--danger)" }}>
                  Disconnect
                </button>
              ) : (
                <button type="button" onClick={() => setShowEmailModal(true)} className="btn btn-primary">
                  Connect
                </button>
              )}
            </div>
          </div>
        ) : (
          <form onSubmit={handleProfileSave}>
            <div style={{ marginBottom: "20px" }}>
              <label className="form-label" style={{ display: "block", marginBottom: "8px", fontWeight: "500" }}>
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
              <label className="form-label" style={{ display: "block", marginBottom: "8px", fontWeight: "500" }}>
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
              <button type="submit" className="btn btn-primary">
                Save Profile
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Credentials Configuration Modal Overlay */}
      {showEmailModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.4)",
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
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
              maxWidth: showGuideSidebar ? "920px" : "460px",
              width: "100%",
              transition: "max-width 0.25s ease-in-out",
              position: "relative",
              animation: "slideUp 0.25s ease-out",
            }}
          >
            {/* MAIN FORM PANEL */}
            <div style={{ flex: 1, padding: "28px", minWidth: "320px", position: "relative" }}>
              {/* Top Left Setup Guide Button */}
              <button
                type="button"
                onClick={() => setShowGuideSidebar(!showGuideSidebar)}
                style={{
                  position: "absolute",
                  top: "22px",
                  left: "24px",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: showGuideSidebar ? "var(--accent)" : "var(--text-secondary)",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "12px",
                  fontWeight: "600",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  backgroundColor: "#f5f5f7",
                }}
                title="Toggle Setup Guide"
              >
                <BookOpen size={15} />
                Setup Guide
              </button>

              {/* Top Right Close Button */}
              <button
                type="button"
                onClick={() => setShowEmailModal(false)}
                style={{
                  position: "absolute",
                  top: "22px",
                  right: "24px",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--text-secondary)",
                }}
              >
                <X size={20} />
              </button>

              <div style={{ marginTop: "32px" }}>
                <h3 style={{ fontSize: "19px", fontWeight: "700", marginBottom: "4px" }}>
                  Configure Email Integration
                </h3>
                <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "20px" }}>
                  Configure IMAP server connection details.
                </p>
              </div>

              <form onSubmit={handleEmailSave}>
                <div style={{ marginBottom: "14px" }}>
                  <label className="form-label" style={{ display: "block", marginBottom: "6px", fontSize: "13px" }}>
                    IMAP Server Host
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    value={emailForm.host}
                    onChange={(e) => setEmailForm((p) => ({ ...p, host: e.target.value }))}
                    style={{ width: "100%", padding: "8px 12px" }}
                    required
                  />
                </div>

                <div style={{ marginBottom: "14px" }}>
                  <label className="form-label" style={{ display: "block", marginBottom: "6px", fontSize: "13px" }}>
                    IMAP Port
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    value={emailForm.port}
                    onChange={(e) => setEmailForm((p) => ({ ...p, port: e.target.value }))}
                    style={{ width: "100%", padding: "8px 12px" }}
                    required
                  />
                </div>

                <div style={{ marginBottom: "14px" }}>
                  <label className="form-label" style={{ display: "block", marginBottom: "6px", fontSize: "13px" }}>
                    Email Address
                  </label>
                  <input
                    type="email"
                    className="form-input"
                    value={emailForm.email}
                    onChange={(e) => setEmailForm((p) => ({ ...p, email: e.target.value }))}
                    style={{ width: "100%", padding: "8px 12px" }}
                    required
                  />
                </div>

                <div style={{ marginBottom: "24px" }}>
                  <label className="form-label" style={{ display: "block", marginBottom: "6px", fontSize: "13px" }}>
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
                    style={{ padding: "8px 16px", fontSize: "13px" }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isConnecting}
                    style={{ padding: "8px 16px", fontSize: "13px" }}
                  >
                    {isConnecting ? "Connecting..." : "Save Connection"}
                  </button>
                </div>
              </form>
            </div>

            {/* EXPANDABLE SIDE SETUP GUIDE */}
            {showGuideSidebar && (
              <div
                style={{
                  width: "460px",
                  borderLeft: "1px solid var(--border-subtle)",
                  backgroundColor: "#fafafa",
                  padding: "28px",
                  display: "flex",
                  flexDirection: "column",
                  animation: "fadeIn 0.2s ease-out",
                  overflowY: "auto",
                  maxHeight: "550px",
                }}
              >
                <h4 style={{ fontSize: "16px", fontWeight: "700", marginBottom: "14px", display: "flex", alignItems: "center", gap: "8px" }}>
                  <BookOpen size={16} color="var(--accent)" />
                  Setup Guide (Gmail / M365)
                </h4>

                <div style={{ display: "flex", flexDirection: "column", gap: "14px", fontSize: "12.5px", lineHeight: "1.4" }}>
                  <div>
                    <div style={{ fontWeight: "600", marginBottom: "3px" }}>1. Enable IMAP Access</div>
                    <div style={{ color: "var(--text-secondary)" }}>
                      Turn on IMAP in Gmail Settings (Forwarding and POP/IMAP) or Office 365 dashboard.
                    </div>
                  </div>

                  <div>
                    <div style={{ fontWeight: "600", marginBottom: "3px" }}>2. Enable Two-Step Verification</div>
                    <div style={{ color: "var(--text-secondary)" }}>
                      Go to <a href="https://myaccount.google.com/" target="_blank" rel="noreferrer" style={{ color: "var(--accent)", textDecoration: "underline" }}>Google Settings</a> &rarr; Security and turn on 2-Step Verification.
                    </div>
                  </div>

                  <div>
                    <div style={{ fontWeight: "600", marginBottom: "3px" }}>3. Generate an App Password</div>
                    <div style={{ color: "var(--text-secondary)" }}>
                      Go to <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" style={{ color: "var(--accent)", textDecoration: "underline" }}>App Passwords</a>, select Mail, and click Create to get your 16-character code.
                    </div>
                  </div>

                  <div style={{
                    background: "#fffbeb",
                    border: "1px solid #fef3c7",
                    color: "#b45309",
                    padding: "8px 10px",
                    borderRadius: "4px",
                    display: "flex",
                    gap: "6px",
                    fontSize: "11px",
                    marginTop: "6px",
                  }}
                  >
                    <ShieldAlert size={14} style={{ flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <strong>Warning:</strong> Never use your normal email password. Only use the generated 16-character App Password.
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mini Animation styles */}
      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: scale(0.95) translateY(10px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
}

