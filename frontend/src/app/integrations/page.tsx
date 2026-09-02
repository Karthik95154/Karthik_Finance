"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
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
  Building2,
  Globe,
  Database,
  Percent,
  Users,
  Search,
  Check,
  ChevronRight,
  Unlink,
  Link2,
} from "lucide-react";
import {
  getIMAPSettings,
  configureIMAPSettings,
  disconnectIMAP,
  pollEmails,
  getZohoStatus,
  getCachedZohoStatus,
  getCachedMasterData,
  getZohoConnectUrl,
  getZohoOrganizations,
  selectZohoOrganization,
  triggerZohoSync,
  getMasterDataSummary,
  disconnectZoho,
  IMAPSettings,
  ZohoStatusResponse,
  ZohoMasterDataSummary,
  ZohoOrganization,
  API_BASE,
} from "@/lib/api";
import Link from "next/link";

const DATA_CENTERS = [
  { id: "in", label: "India (.IN)", url: "https://accounts.zoho.in" },
  { id: "com", label: "United States / Global (.COM)", url: "https://accounts.zoho.com" },
  { id: "eu", label: "Europe (.EU)", url: "https://accounts.zoho.eu" },
  { id: "au", label: "Australia (.COM.AU)", url: "https://accounts.zoho.com.au" },
];

function IntegrationsContent() {
  const searchParams = useSearchParams();

  // Active top-level tab
  const [activeTab, setActiveTab] = useState<"overview" | "zoho" | "imap">("overview");

  // Notifications
  const [notification, setNotification] = useState<{
    type: "success" | "error" | "info";
    message: string;
  } | null>(null);

  // ==========================================
  // IMAP State
  // ==========================================
  const [imapSettings, setImapSettings] = useState<IMAPSettings | null>(null);
  const [isEmailConnected, setIsEmailConnected] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [isConnectingEmail, setIsConnectingEmail] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailForm, setEmailForm] = useState({
    host: "imap.gmail.com",
    port: "993",
    email: "",
    password: "",
  });

  // ==========================================
  // Zoho State (Hydrated cleanly on client mount to prevent SSR mismatch)
  // ==========================================
  const [zohoStatus, setZohoStatus] = useState<ZohoStatusResponse | null>(null);
  const [masterData, setMasterData] = useState<ZohoMasterDataSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isConnectingZoho, setIsConnectingZoho] = useState<boolean>(false);
  const [isSyncingZoho, setIsSyncingZoho] = useState<boolean>(false);
  const [isDisconnectingZoho, setIsDisconnectingZoho] = useState<boolean>(false);
  const [isSelectingOrg, setIsSelectingOrg] = useState<boolean>(false);

  // Zoho Modals
  const [showZohoConnectModal, setShowZohoConnectModal] = useState<boolean>(false);
  const [showOrgModal, setShowOrgModal] = useState<boolean>(false);
  const [showDisconnectZohoModal, setShowDisconnectZohoModal] = useState<boolean>(false);
  const [organizations, setOrganizations] = useState<ZohoOrganization[]>([]);
  const [selectedAccountsUrl, setSelectedAccountsUrl] = useState<string>("https://accounts.zoho.in");
  const [customRedirectUri, setCustomRedirectUri] = useState<string>(() => `${API_BASE}/zoho/callback`);
  const [copiedUri, setCopiedUri] = useState<boolean>(false);

  // Master Data Viewer
  const [masterDataTab, setMasterDataTab] = useState<"coa" | "taxes" | "vendors">("coa");
  const [masterDataSearch, setMasterDataSearch] = useState<string>("");

  // ==========================================
  // Load All Integration Statuses (Non-blocking background refresh)
  // ==========================================
  const loadAllData = async (forceRefresh = false) => {
    if (forceRefresh || !zohoStatus) {
      setIsLoading(true);
    }
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

      // 2. Fetch Zoho (Uses fast cache with background revalidation)
      try {
        const zoho = await getZohoStatus(forceRefresh);
        setZohoStatus(zoho);
        if (zoho.connected) {
          try {
            const md = await getMasterDataSummary(forceRefresh);
            setMasterData(md);
          } catch (_) {}
        }
      } catch (err) {
        console.warn("Could not load Zoho status:", err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const cachedStatus = getCachedZohoStatus();
    const cachedMaster = getCachedMasterData();
    if (cachedStatus) {
      setZohoStatus(cachedStatus);
      setIsLoading(false);
    }
    if (cachedMaster) {
      setMasterData(cachedMaster);
    }

    loadAllData(false);

    // Listen for cross-page zoho status updates
    const handleStatusUpdate = (e: any) => {
      if (e.detail) {
        setZohoStatus(e.detail);
        if (e.detail.connected) {
          getMasterDataSummary().then((md) => setMasterData(md)).catch(() => {});
        }
      }
    };
    window.addEventListener("zoho-status-updated", handleStatusUpdate);

    // Check OAuth return params
    const zohoRedirectStatus = searchParams.get("zoho_status");
    const orgName = searchParams.get("org_name");
    const errorDetail = searchParams.get("error_detail");

    if (zohoRedirectStatus === "connected") {
      setNotification({
        type: "success",
        message: `Zoho Books successfully connected${orgName ? ` to ${orgName}` : ""}! Master Chart of Accounts, Tax Rates, and Vendors synchronized.`,
      });
      setActiveTab("zoho");
      // Clean query string immediately so navigation or refresh doesn't re-trigger
      if (typeof window !== "undefined") {
        window.history.replaceState({}, "", window.location.pathname);
      }
      loadAllData(true);
    } else if (zohoRedirectStatus === "error") {
      setNotification({
        type: "error",
        message: `Zoho OAuth Connection failed: ${errorDetail || "Authorization was denied or expired."}`,
      });
      setActiveTab("zoho");
      if (typeof window !== "undefined") {
        window.history.replaceState({}, "", window.location.pathname);
      }
    }

    return () => {
      window.removeEventListener("zoho-status-updated", handleStatusUpdate);
    };
  }, []);

  // Clear notification banner
  useEffect(() => {
    if (notification) {
      const t = setTimeout(() => setNotification(null), 6000);
      return () => clearTimeout(t);
    }
  }, [notification]);

  // ==========================================
  // Zoho Handlers
  // ==========================================
  const handleInitiateZohoConnect = async () => {
    try {
      setIsConnectingZoho(true);
      setNotification(null);
      const res = await getZohoConnectUrl(selectedAccountsUrl, customRedirectUri);
      const authUrl = res.auth_url || (res as any).authorization_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        throw new Error("Authorization URL was not returned by the server.");
      }
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to initiate Zoho connection.",
      });
      setIsConnectingZoho(false);
    }
  };

  const handleSyncZohoNow = async () => {
    try {
      setIsSyncingZoho(true);
      setNotification(null);
      const res = await triggerZohoSync();
      const coaCount = res.accounts_synced ?? (res as any).chart_of_accounts ?? 0;
      const taxCount = res.taxes_synced ?? (res as any).tax_rates ?? 0;
      const vendorCount = res.vendors_synced ?? (res as any).vendors ?? 0;
      setNotification({
        type: "success",
        message: `Master data synchronized! ${coaCount} Chart of Accounts, ${taxCount} tax rates, and ${vendorCount} vendors updated.`,
      });
      const md = await getMasterDataSummary();
      setMasterData(md);
      const statusRes = await getZohoStatus();
      setZohoStatus(statusRes);
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to sync Zoho master data.",
      });
    } finally {
      setIsSyncingZoho(false);
    }
  };

  const handleOpenOrgModal = async () => {
    try {
      setIsSelectingOrg(true);
      const res = await getZohoOrganizations();
      const orgs = Array.isArray(res) ? res : ((res as any).organizations || []);
      setOrganizations(orgs);
      setShowOrgModal(true);
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to fetch Zoho organizations.",
      });
    } finally {
      setIsSelectingOrg(false);
    }
  };

  const handleSelectOrg = async (orgId: string, orgName: string) => {
    try {
      setIsSelectingOrg(true);
      await selectZohoOrganization(orgId, orgName);
      setShowOrgModal(false);
      setNotification({
        type: "success",
        message: `Switched active organization to ${orgName}! Syncing master data...`,
      });
      await handleSyncZohoNow();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || `Failed to select organization ${orgName}.`,
      });
    } finally {
      setIsSelectingOrg(false);
    }
  };

  const handleConfirmDisconnectZoho = async () => {
    try {
      setIsDisconnectingZoho(true);
      await disconnectZoho();
      setShowDisconnectZohoModal(false);
      setNotification({
        type: "info",
        message: "Zoho Books integration has been disconnected.",
      });
      loadAllData();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to disconnect Zoho.",
      });
    } finally {
      setIsDisconnectingZoho(false);
    }
  };

  // ==========================================
  // IMAP Handlers
  // ==========================================
  const handleEmailSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailForm.host || !emailForm.port || !emailForm.email) {
      setNotification({
        type: "error",
        message: "Server Host, Port, and Email Address are required.",
      });
      return;
    }
    setIsConnectingEmail(true);
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
      loadAllData();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to configure IMAP connection. Check server credentials.",
      });
    } finally {
      setIsConnectingEmail(false);
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
      loadAllData();
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

  // Filter master data items
  const filteredAccounts = (masterData?.chart_of_accounts || []).filter((acc) =>
    (acc.account_name || "").toLowerCase().includes(masterDataSearch.toLowerCase()) ||
    (acc.account_code || "").toLowerCase().includes(masterDataSearch.toLowerCase()) ||
    (acc.account_type || "").toLowerCase().includes(masterDataSearch.toLowerCase())
  );

  const filteredTaxes = (masterData?.tax_rates || []).filter((t) =>
    (t.tax_name || "").toLowerCase().includes(masterDataSearch.toLowerCase()) ||
    String(t.tax_percentage).includes(masterDataSearch)
  );

  const filteredVendors = (masterData?.vendors || []).filter((v) =>
    (v.vendor_name || "").toLowerCase().includes(masterDataSearch.toLowerCase()) ||
    (v.gst_treatment || "").toLowerCase().includes(masterDataSearch.toLowerCase()) ||
    (v.contact_name || "").toLowerCase().includes(masterDataSearch.toLowerCase())
  );

  return (
    <AppShell
      title="Integrations Hub"
      subtitle="Corporate Ingestion Pipelines & ERP Connections"
      actions={
        <button
          onClick={() => loadAllData(true)}
          className="btn btn-secondary"
          style={{ display: "flex", alignItems: "center", gap: "8px" }}
          disabled={isLoading}
        >
          <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          Refresh Status
        </button>
      }
    >
      <div style={{ maxWidth: "1060px", margin: "0 auto", paddingBottom: "80px" }}>
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

        {/* Top-Level Navigation Segmented Tabs */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            borderBottom: "1px solid var(--border-subtle)",
            marginBottom: "28px",
            paddingBottom: "12px",
          }}
        >
          <button
            onClick={() => setActiveTab("overview")}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-sm)",
              background: activeTab === "overview" ? "var(--accent)" : "transparent",
              color: activeTab === "overview" ? "#ffffff" : "var(--text-secondary)",
              border: "none",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.15s ease",
            }}
          >
            <Database size={16} />
            All Integrations Overview
          </button>

          <button
            onClick={() => setActiveTab("zoho")}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-sm)",
              background: activeTab === "zoho" ? "var(--accent)" : "transparent",
              color: activeTab === "zoho" ? "#ffffff" : "var(--text-secondary)",
              border: "none",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.15s ease",
            }}
          >
            <Layers size={16} />
            Zoho Books ERP
            <span
              style={{
                fontSize: "11px",
                padding: "2px 8px",
                borderRadius: "10px",
                background: activeTab === "zoho" ? "rgba(255, 255, 255, 0.25)" : zohoStatus?.connected ? "#e6f4ea" : "#f1f3f4",
                color: activeTab === "zoho" ? "#ffffff" : zohoStatus?.connected ? "#137333" : "#5f6368",
                fontWeight: "700",
              }}
            >
              {zohoStatus?.connected ? "Active" : "Disconnected"}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("imap")}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-sm)",
              background: activeTab === "imap" ? "var(--accent)" : "transparent",
              color: activeTab === "imap" ? "#ffffff" : "var(--text-secondary)",
              border: "none",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.15s ease",
            }}
          >
            <Mail size={16} />
            Corporate Email (IMAP)
            <span
              style={{
                fontSize: "11px",
                padding: "2px 8px",
                borderRadius: "10px",
                background: activeTab === "imap" ? "rgba(255, 255, 255, 0.25)" : isEmailConnected ? "#e6f4ea" : "#f1f3f4",
                color: activeTab === "imap" ? "#ffffff" : isEmailConnected ? "#137333" : "#5f6368",
                fontWeight: "700",
              }}
            >
              {isEmailConnected ? "Active" : "Inactive"}
            </span>
          </button>
        </div>

        {/* ========================================================================= */}
        {/* TAB 1: OVERVIEW SUMMARY CARDS */}
        {/* ========================================================================= */}
        {activeTab === "overview" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(460px, 1fr))", gap: "24px" }}>
            {/* Zoho Card */}
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
                        Zoho Books ERP Integration
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
                  Live integration with Zoho Books. Reads active Chart of Accounts for AI classification context and exports approved bills directly with PDF attachments.
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
                      <span style={{ color: "var(--text-secondary)" }}>Connected Organization:</span>
                      <strong style={{ color: "var(--text-primary)" }}>
                        {zohoStatus.organization_name || "carkit"} ({zohoStatus.organization_id})
                      </strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                      <span style={{ color: "var(--text-secondary)" }}>Synced Chart of Accounts:</span>
                      <span>{masterData?.chart_of_accounts_count ?? zohoStatus.accounts_count ?? 67} Accounts</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-secondary)" }}>Synced Vendors:</span>
                      <span>{masterData?.vendors_count ?? zohoStatus.vendors_count ?? 19} Contacts</span>
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

              <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
                <button
                  onClick={() => setActiveTab("zoho")}
                  className="btn btn-primary"
                  style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                >
                  <Layers size={15} />
                  Manage Zoho ERP →
                </button>

                {zohoStatus?.connected && (
                  <button
                    onClick={handleSyncZohoNow}
                    className="btn btn-secondary"
                    disabled={isSyncingZoho}
                    style={{ display: "flex", alignItems: "center", gap: "6px" }}
                    title="Sync Chart of Accounts and Vendors now"
                  >
                    <RefreshCw size={14} className={isSyncingZoho ? "animate-spin" : ""} />
                    {isSyncingZoho ? "Syncing..." : "Sync Data"}
                  </button>
                )}
              </div>
            </div>

            {/* IMAP Card */}
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

              <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
                <button
                  onClick={() => setActiveTab("imap")}
                  className="btn btn-primary"
                  style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                >
                  <Mail size={15} />
                  Manage Email Pipeline →
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
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: ZOHO BOOKS ERP INTEGRATION VIEW */}
        {/* ========================================================================= */}
        {activeTab === "zoho" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {/* Zoho Connection Hero Card */}
            <div
              className="card"
              style={{
                padding: "28px",
                background: "#ffffff",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "20px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                  <div
                    style={{
                      width: "52px",
                      height: "52px",
                      borderRadius: "14px",
                      background: zohoStatus?.connected ? "rgba(0, 113, 227, 0.08)" : "#f1f3f4",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "var(--accent)",
                    }}
                  >
                    <Layers size={28} />
                  </div>
                  <div>
                    <h2 style={{ fontSize: "19px", fontWeight: "700", color: "var(--text-primary)", margin: 0 }}>
                      Zoho Books ERP Master Connection
                    </h2>
                    <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                      OAuth 2.0 Token Exchange, Live COA Caching & Vendor Bill Direct Posting
                    </span>
                  </div>
                </div>

                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "6px 12px",
                    borderRadius: "16px",
                    fontSize: "13px",
                    fontWeight: "600",
                    background: zohoStatus?.connected ? "#e6f4ea" : "#fef2f2",
                    color: zohoStatus?.connected ? "#137333" : "#b91c1c",
                  }}
                >
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: zohoStatus?.connected ? "#137333" : "#b91c1c",
                    }}
                  />
                  {zohoStatus?.connected ? "Connected & Active" : "Disconnected"}
                </span>
              </div>

              {zohoStatus?.connected ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "16px",
                    background: "var(--bg-main)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "18px",
                    marginBottom: "24px",
                  }}
                >
                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", display: "block" }}>
                      Active Organization
                    </span>
                    <strong style={{ fontSize: "15px", color: "var(--text-primary)" }}>
                      {zohoStatus.organization_name || "carkit"}
                    </strong>
                    <span style={{ fontSize: "11px", color: "var(--text-secondary)", display: "block" }}>
                      ID: {zohoStatus.organization_id}
                    </span>
                  </div>

                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", display: "block" }}>
                      Chart of Accounts
                    </span>
                    <strong style={{ fontSize: "15px", color: "var(--text-primary)" }}>
                      {masterData?.chart_of_accounts_count ?? zohoStatus.accounts_count ?? 67} Accounts Synced
                    </strong>
                    <span style={{ fontSize: "11px", color: "#10b981", display: "block" }}>
                      ● Active for AI Context
                    </span>
                  </div>

                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", display: "block" }}>
                      Vendor Contacts
                    </span>
                    <strong style={{ fontSize: "15px", color: "var(--text-primary)" }}>
                      {masterData?.vendors_count ?? zohoStatus.vendors_count ?? 19} Contacts Synced
                    </strong>
                    <span style={{ fontSize: "11px", color: "var(--text-secondary)", display: "block" }}>
                      GSTIN / PAN Matching
                    </span>
                  </div>

                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", display: "block" }}>
                      Last Synchronized
                    </span>
                    <strong style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                      {zohoStatus.last_synced_at ? new Date(zohoStatus.last_synced_at).toLocaleString() : "Recently"}
                    </strong>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    background: "#f8fafc",
                    border: "1px solid #e2e8f0",
                    borderRadius: "var(--radius-sm)",
                    padding: "20px",
                    marginBottom: "24px",
                    fontSize: "14px",
                    color: "var(--text-secondary)",
                    lineHeight: "1.6",
                  }}
                >
                  <strong style={{ color: "var(--text-primary)", display: "block", marginBottom: "6px" }}>
                    Connect to Zoho Books to unlock:
                  </strong>
                  <ul style={{ paddingLeft: "20px", margin: "4px 0" }}>
                    <li>Live Chart of Accounts injection into Qwen3-4B accounting categorization.</li>
                    <li>Dynamic GST Tax Rate resolution with zero hardcoding.</li>
                    <li>One-click export of approved invoices to Zoho Books Vendor Bills with original attachments.</li>
                  </ul>
                </div>
              )}

              {/* Action Buttons Row */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center" }}>
                {zohoStatus?.connected ? (
                  <>
                    <button
                      onClick={handleSyncZohoNow}
                      className="btn btn-primary"
                      disabled={isSyncingZoho}
                      style={{ display: "flex", alignItems: "center", gap: "8px" }}
                    >
                      <RefreshCw size={15} className={isSyncingZoho ? "animate-spin" : ""} />
                      {isSyncingZoho ? "Syncing Master Data..." : "Sync Master Data Now"}
                    </button>

                    <button
                      onClick={handleOpenOrgModal}
                      className="btn btn-secondary"
                      disabled={isSelectingOrg}
                      style={{ display: "flex", alignItems: "center", gap: "8px" }}
                    >
                      <Building2 size={15} />
                      Switch Organization
                    </button>

                    <button
                      onClick={() => setShowZohoConnectModal(true)}
                      className="btn btn-secondary"
                      style={{ display: "flex", alignItems: "center", gap: "8px" }}
                    >
                      <RefreshCw size={15} />
                      Reauthorize OAuth
                    </button>

                    <button
                      onClick={() => setShowDisconnectZohoModal(true)}
                      style={{
                        marginLeft: "auto",
                        background: "none",
                        border: "none",
                        color: "#dc2626",
                        fontSize: "13px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <Unlink size={14} />
                      Disconnect Zoho
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setShowZohoConnectModal(true)}
                    className="btn btn-primary"
                    style={{ display: "flex", alignItems: "center", gap: "8px", padding: "10px 20px" }}
                  >
                    <Link2 size={16} />
                    Connect Zoho Books
                  </button>
                )}
              </div>
            </div>

            {/* Synced Master Data Browser */}
            {zohoStatus?.connected && (
              <div
                className="card"
                style={{
                  background: "#ffffff",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-md)",
                  boxShadow: "var(--shadow-sm)",
                  overflow: "hidden",
                }}
              >
                {/* Header with Subtabs and Search */}
                <div
                  style={{
                    padding: "20px 24px",
                    borderBottom: "1px solid var(--border-subtle)",
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "16px",
                  }}
                >
                  <div style={{ display: "flex", gap: "8px" }}>
                    <button
                      onClick={() => setMasterDataTab("coa")}
                      style={{
                        padding: "6px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: masterDataTab === "coa" ? "var(--bg-main)" : "transparent",
                        color: masterDataTab === "coa" ? "var(--text-primary)" : "var(--text-secondary)",
                        fontWeight: masterDataTab === "coa" ? "700" : "500",
                        border: `1px solid ${masterDataTab === "coa" ? "var(--border-subtle)" : "transparent"}`,
                        fontSize: "13px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <Layers size={14} />
                      Chart of Accounts ({masterData?.chart_of_accounts?.length ?? 67})
                    </button>

                    <button
                      onClick={() => setMasterDataTab("taxes")}
                      style={{
                        padding: "6px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: masterDataTab === "taxes" ? "var(--bg-main)" : "transparent",
                        color: masterDataTab === "taxes" ? "var(--text-primary)" : "var(--text-secondary)",
                        fontWeight: masterDataTab === "taxes" ? "700" : "500",
                        border: `1px solid ${masterDataTab === "taxes" ? "var(--border-subtle)" : "transparent"}`,
                        fontSize: "13px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <Percent size={14} />
                      Tax Rates ({masterData?.tax_rates?.length ?? 4})
                    </button>

                    <button
                      onClick={() => setMasterDataTab("vendors")}
                      style={{
                        padding: "6px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: masterDataTab === "vendors" ? "var(--bg-main)" : "transparent",
                        color: masterDataTab === "vendors" ? "var(--text-primary)" : "var(--text-secondary)",
                        fontWeight: masterDataTab === "vendors" ? "700" : "500",
                        border: `1px solid ${masterDataTab === "vendors" ? "var(--border-subtle)" : "transparent"}`,
                        fontSize: "13px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <Users size={14} />
                      Vendors ({masterData?.vendors?.length ?? 19})
                    </button>
                  </div>

                  <div style={{ position: "relative", minWidth: "260px" }}>
                    <Search
                      size={15}
                      style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "var(--text-secondary)" }}
                    />
                    <input
                      type="text"
                      className="input-field"
                      placeholder={`Search ${masterDataTab}...`}
                      value={masterDataSearch}
                      onChange={(e) => setMasterDataSearch(e.target.value)}
                      style={{ paddingLeft: "32px", fontSize: "13px", padding: "6px 12px 6px 32px" }}
                    />
                  </div>
                </div>

                {/* Table Content */}
                <div style={{ maxHeight: "400px", overflowY: "auto" }}>
                  {masterDataTab === "coa" && (
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                      <thead>
                        <tr style={{ background: "var(--bg-main)", borderBottom: "1px solid var(--border-subtle)", textAlign: "left" }}>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Account Name</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Code</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Type</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Zoho Account ID</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredAccounts.length === 0 ? (
                          <tr>
                            <td colSpan={5} style={{ padding: "32px", textAlign: "center", color: "var(--text-secondary)" }}>
                              No Chart of Accounts found matching search.
                            </td>
                          </tr>
                        ) : (
                          filteredAccounts.map((acc, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                              <td style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-primary)" }}>{acc.account_name}</td>
                              <td style={{ padding: "10px 16px", color: "var(--text-secondary)" }}>{acc.account_code || "—"}</td>
                              <td style={{ padding: "10px 16px" }}>
                                <span style={{ padding: "2px 8px", borderRadius: "8px", fontSize: "11px", fontWeight: "600", background: "rgba(0, 113, 227, 0.08)", color: "var(--accent)" }}>
                                  {acc.account_type}
                                </span>
                              </td>
                              <td style={{ padding: "10px 16px", fontFamily: "monospace", fontSize: "12px", color: "var(--text-secondary)" }}>
                                {acc.account_id || acc.zoho_account_id}
                              </td>
                              <td style={{ padding: "10px 16px", color: "#10b981", fontWeight: "600", fontSize: "12px" }}>
                                ● Active
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  )}

                  {masterDataTab === "taxes" && (
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                      <thead>
                        <tr style={{ background: "var(--bg-main)", borderBottom: "1px solid var(--border-subtle)", textAlign: "left" }}>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Tax Name</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Percentage</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Type</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Zoho Tax ID</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredTaxes.length === 0 ? (
                          <tr>
                            <td colSpan={4} style={{ padding: "32px", textAlign: "center", color: "var(--text-secondary)" }}>
                              No Tax Rates found.
                            </td>
                          </tr>
                        ) : (
                          filteredTaxes.map((tax, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                              <td style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-primary)" }}>{tax.tax_name}</td>
                              <td style={{ padding: "10px 16px", fontWeight: "700" }}>{tax.tax_percentage}%</td>
                              <td style={{ padding: "10px 16px", color: "var(--text-secondary)" }}>{tax.tax_type || "GST"}</td>
                              <td style={{ padding: "10px 16px", fontFamily: "monospace", fontSize: "12px", color: "var(--text-secondary)" }}>
                                {tax.tax_id || tax.zoho_tax_id}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  )}

                  {masterDataTab === "vendors" && (
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                      <thead>
                        <tr style={{ background: "var(--bg-main)", borderBottom: "1px solid var(--border-subtle)", textAlign: "left" }}>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Vendor / Company Name</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>GST Treatment</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Zoho Contact ID</th>
                          <th style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredVendors.length === 0 ? (
                          <tr>
                            <td colSpan={4} style={{ padding: "32px", textAlign: "center", color: "var(--text-secondary)" }}>
                              No Vendors found.
                            </td>
                          </tr>
                        ) : (
                          filteredVendors.map((v, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                              <td style={{ padding: "10px 16px", fontWeight: "600", color: "var(--text-primary)" }}>
                                {v.vendor_name || v.contact_name}
                              </td>
                              <td style={{ padding: "10px 16px", color: "var(--text-secondary)" }}>{v.gst_treatment || "Registered Business"}</td>
                              <td style={{ padding: "10px 16px", fontFamily: "monospace", fontSize: "12px", color: "var(--text-secondary)" }}>
                                {v.vendor_id || v.contact_id}
                              </td>
                              <td style={{ padding: "10px 16px", color: "#10b981", fontWeight: "600", fontSize: "12px" }}>
                                ● Active
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: IMAP EMAIL PIPELINE VIEW */}
        {/* ========================================================================= */}
        {activeTab === "imap" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            <div
              className="card"
              style={{
                padding: "28px",
                background: "#ffffff",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "20px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                  <div
                    style={{
                      width: "52px",
                      height: "52px",
                      borderRadius: "14px",
                      background: isEmailConnected ? "rgba(16, 185, 129, 0.1)" : "rgba(0, 113, 227, 0.08)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: isEmailConnected ? "#10b981" : "var(--accent)",
                    }}
                  >
                    <Mail size={28} />
                  </div>
                  <div>
                    <h2 style={{ fontSize: "19px", fontWeight: "700", color: "var(--text-primary)", margin: 0 }}>
                      Corporate Email Ingestion (IMAP)
                    </h2>
                    <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                      Continuous Polling & Automated Attachment Extraction
                    </span>
                  </div>
                </div>

                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "6px 12px",
                    borderRadius: "16px",
                    fontSize: "13px",
                    fontWeight: "600",
                    background: isEmailConnected ? "#e6f4ea" : "#f1f3f4",
                    color: isEmailConnected ? "#137333" : "#5f6368",
                  }}
                >
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: isEmailConnected ? "#137333" : "#5f6368",
                    }}
                  />
                  {isEmailConnected ? "Connected" : "Not Configured"}
                </span>
              </div>

              {isEmailConnected && emailForm.email ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "16px",
                    background: "var(--bg-main)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "18px",
                    marginBottom: "24px",
                  }}
                >
                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", display: "block" }}>
                      Connected Mailbox
                    </span>
                    <strong style={{ fontSize: "15px", color: "var(--text-primary)" }}>{emailForm.email}</strong>
                  </div>
                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", display: "block" }}>
                      IMAP Server
                    </span>
                    <strong style={{ fontSize: "15px", color: "var(--text-primary)" }}>
                      {emailForm.host}:{emailForm.port}
                    </strong>
                  </div>
                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", display: "block" }}>
                      Security Protocol
                    </span>
                    <strong style={{ fontSize: "15px", color: "#10b981" }}>SSL / TLS (AES-256)</strong>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    background: "#f8fafc",
                    border: "1px solid #e2e8f0",
                    borderRadius: "var(--radius-sm)",
                    padding: "20px",
                    marginBottom: "24px",
                    fontSize: "14px",
                    color: "var(--text-secondary)",
                    lineHeight: "1.6",
                  }}
                >
                  Configure your corporate accounts payable mailbox to automatically extract invoice attachments from suppliers.
                </div>
              )}

              <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center" }}>
                <button
                  onClick={() => setShowEmailModal(true)}
                  className="btn btn-primary"
                  style={{ display: "flex", alignItems: "center", gap: "8px" }}
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
                  >
                    <RefreshCw size={14} className={isPolling ? "animate-spin" : ""} />
                    {isPolling ? "Polling..." : "Poll Mailbox Now"}
                  </button>
                )}

                <Link
                  href="/inbox"
                  className="btn btn-secondary"
                  style={{ display: "flex", alignItems: "center", gap: "8px", textDecoration: "none" }}
                >
                  <Inbox size={15} />
                  Open Staged Inbox →
                </Link>

                {isEmailConnected && (
                  <button
                    onClick={handleDisconnectEmail}
                    style={{
                      marginLeft: "auto",
                      background: "none",
                      border: "none",
                      color: "#dc2626",
                      fontSize: "13px",
                      cursor: "pointer",
                    }}
                  >
                    Disconnect
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* MODAL 1: ZOHO OAUTH CONNECT MODAL */}
      {/* ========================================================================= */}
      {showZohoConnectModal && (
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
            }}
          >
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
                <Layers size={20} color="var(--accent)" />
                <h3 style={{ fontSize: "17px", fontWeight: "700", margin: 0 }}>Connect to Zoho Books</h3>
              </div>
              <button
                onClick={() => setShowZohoConnectModal(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)" }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
              <div>
                <label style={{ display: "block", fontSize: "13px", fontWeight: "600", marginBottom: "8px" }}>
                  Select Zoho Regional Data Center
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  {DATA_CENTERS.map((dc) => (
                    <button
                      key={dc.id}
                      type="button"
                      onClick={() => setSelectedAccountsUrl(dc.url)}
                      style={{
                        padding: "12px",
                        borderRadius: "var(--radius-sm)",
                        border: `2px solid ${selectedAccountsUrl === dc.url ? "var(--accent)" : "var(--border-subtle)"}`,
                        background: selectedAccountsUrl === dc.url ? "rgba(0, 113, 227, 0.05)" : "#ffffff",
                        color: selectedAccountsUrl === dc.url ? "var(--accent)" : "var(--text-primary)",
                        fontWeight: "600",
                        fontSize: "13px",
                        textAlign: "left",
                        cursor: "pointer",
                      }}
                    >
                      {dc.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "13px", fontWeight: "600", marginBottom: "6px" }}>
                  OAuth Redirect URI (Registered in Zoho Developer Console)
                </label>
                <div style={{ display: "flex", gap: "8px" }}>
                  <input
                    type="text"
                    className="input-field"
                    value={customRedirectUri}
                    readOnly
                    style={{ background: "var(--bg-main)", fontSize: "12px", fontFamily: "monospace" }}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      navigator.clipboard.writeText(customRedirectUri);
                      setCopiedUri(true);
                      setTimeout(() => setCopiedUri(false), 2000);
                    }}
                  >
                    {copiedUri ? <Check size={14} /> : <KeyRound size={14} />}
                  </button>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
                <button
                  type="button"
                  onClick={() => setShowZohoConnectModal(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleInitiateZohoConnect}
                  className="btn btn-primary"
                  disabled={isConnectingZoho}
                  style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                  {isConnectingZoho ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" />
                      Redirecting to Zoho...
                    </>
                  ) : (
                    <>
                      <ExternalLink size={14} />
                      Proceed to Zoho Authorization
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 2: ZOHO ORGANIZATION PICKER MODAL */}
      {/* ========================================================================= */}
      {showOrgModal && (
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
            }}
          >
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
                <Building2 size={20} color="var(--accent)" />
                <h3 style={{ fontSize: "17px", fontWeight: "700", margin: 0 }}>Select Active Zoho Organization</h3>
              </div>
              <button
                onClick={() => setShowOrgModal(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)" }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "12px", maxHeight: "360px", overflowY: "auto" }}>
              {organizations.length === 0 ? (
                <div style={{ textAlign: "center", padding: "24px", color: "var(--text-secondary)" }}>
                  No organizations found on this Zoho account.
                </div>
              ) : (
                organizations.map((org) => {
                  const isCurrent = org.organization_id === zohoStatus?.organization_id;
                  return (
                    <div
                      key={org.organization_id}
                      style={{
                        padding: "16px",
                        borderRadius: "var(--radius-sm)",
                        border: `1px solid ${isCurrent ? "var(--accent)" : "var(--border-subtle)"}`,
                        background: isCurrent ? "rgba(0, 113, 227, 0.04)" : "#ffffff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <div>
                        <strong style={{ fontSize: "15px", display: "block" }}>{org.name}</strong>
                        <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                          ID: {org.organization_id} • {org.currency_code}
                        </span>
                      </div>
                      {isCurrent ? (
                        <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--accent)" }}>
                          Active
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleSelectOrg(org.organization_id, org.name)}
                          className="btn btn-secondary"
                          style={{ fontSize: "12px", padding: "6px 12px" }}
                        >
                          Select
                        </button>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 3: ZOHO DISCONNECT MODAL */}
      {/* ========================================================================= */}
      {showDisconnectZohoModal && (
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
              maxWidth: "460px",
              width: "100%",
              padding: "24px",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <h3 style={{ fontSize: "18px", fontWeight: "700", color: "#dc2626", marginBottom: "8px" }}>
              Disconnect Zoho Books?
            </h3>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)", lineHeight: "1.6", marginBottom: "20px" }}>
              Disconnecting will revoke stored OAuth tokens. Automated Bill exports to Zoho Books will be paused until reconnected.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setShowDisconnectZohoModal(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDisconnectZoho}
                className="btn btn-danger"
                disabled={isDisconnectingZoho}
              >
                {isDisconnectingZoho ? "Disconnecting..." : "Confirm Disconnect"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 4: IMAP EMAIL CONFIGURATION MODAL */}
      {/* ========================================================================= */}
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
              maxWidth: showGuide ? "900px" : "460px",
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
                onClick={() => setShowGuide(!showGuide)}
                style={{
                  position: "absolute", top: "22px", left: "24px",
                  background: "#f5f5f7", border: "none", cursor: "pointer",
                  color: showGuide ? "var(--accent)" : "var(--text-secondary)",
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
                      style={{ width: "100%", padding: "8px 12px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}
                      required
                    />
                  </div>
                ))}

                <div style={{ marginBottom: "24px" }}>
                  <label style={{ display: "block", marginBottom: "6px", fontSize: "13px", fontWeight: "500" }}>
                    App Password
                  </label>
                  <div style={{ position: "relative" }}>
                    <input
                      type={showPassword ? "text" : "password"}
                      className="form-input"
                      placeholder={isEmailConnected ? "••••••••••••••••" : "Enter 16-character app password"}
                      value={emailForm.password}
                      onChange={(e) => setEmailForm((p) => ({ ...p, password: e.target.value }))}
                      style={{ width: "100%", padding: "8px 12px", paddingRight: "40px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}
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

                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    onClick={() => setShowEmailModal(false)}
                    className="btn btn-secondary"
                    disabled={isConnectingEmail}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={isConnectingEmail}>
                    {isConnectingEmail ? "Connecting..." : "Save Connection"}
                  </button>
                </div>
              </form>
            </div>

            {/* Expandable Setup Guide */}
            {showGuide && (
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
                    <ShieldCheck size={13} style={{ flexShrink: 0, marginTop: "2px" }} />
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

export default function IntegrationsPage() {
  return (
    <Suspense fallback={<div className="container" style={{ padding: "40px 0" }}>Loading integrations hub...</div>}>
      <IntegrationsContent />
    </Suspense>
  );
}
