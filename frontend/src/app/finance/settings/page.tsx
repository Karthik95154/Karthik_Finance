"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  CheckCircle2,
  XCircle,
  RefreshCw,
  Unlink,
  Link2,
  Building2,
  Globe,
  Database,
  Layers,
  Percent,
  Users,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  UserCheck,
  Check,
  ChevronRight,
  Info,
  Search,
  BookOpen,
  Calendar,
  Lock,
  Copy,
} from "lucide-react";
import {
  getZohoStatus,
  getCachedZohoStatus,
  getCachedMasterData,
  getZohoConnectUrl,
  getZohoOrganizations,
  selectZohoOrganization,
  triggerZohoSync,
  getMasterDataSummary,
  disconnectZoho,
  getCurrentUser,
  switchDevRole,
  ZohoStatusResponse,
  ZohoOrganization,
  ZohoMasterDataSummary,
  UserProfile,
  ZohoConnectionState,
  API_BASE,
} from "@/lib/api";

const DATA_CENTERS = [
  { id: "in", label: "India (.IN)", url: "https://accounts.zoho.in" },
  { id: "com", label: "United States / Global (.COM)", url: "https://accounts.zoho.com" },
  { id: "eu", label: "Europe (.EU)", url: "https://accounts.zoho.eu" },
  { id: "au", label: "Australia (.COM.AU)", url: "https://accounts.zoho.com.au" },
];

function SettingsContent() {
  const searchParams = useSearchParams();

  // Core state (Initialized from cache for instant stable display)
  const [zohoStatus, setZohoStatus] = useState<ZohoStatusResponse | null>(() => getCachedZohoStatus());
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [masterData, setMasterData] = useState<ZohoMasterDataSummary | null>(() => getCachedMasterData());
  const [isLoading, setIsLoading] = useState<boolean>(() => !getCachedZohoStatus());

  // Active UI tab for master data tables
  const [activeTab, setActiveTab] = useState<"overview" | "coa" | "taxes" | "vendors">("overview");
  const [searchTerm, setSearchTerm] = useState<string>("");

  // Action states
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isDisconnecting, setIsDisconnecting] = useState<boolean>(false);
  const [isSelectingOrg, setIsSelectingOrg] = useState<boolean>(false);
  const [isSwitchingRole, setIsSwitchingRole] = useState<boolean>(false);

  // Modals & organization selection
  const [organizations, setOrganizations] = useState<ZohoOrganization[]>([]);
  const [showOrgModal, setShowOrgModal] = useState<boolean>(false);
  const [showDisconnectModal, setShowDisconnectModal] = useState<boolean>(false);
  const [selectedAccountsUrl, setSelectedAccountsUrl] = useState<string>("https://accounts.zoho.in");
  const [customRedirectUri, setCustomRedirectUri] = useState<string>(() => `${API_BASE}/zoho/callback`);
  const [copiedUri, setCopiedUri] = useState<boolean>(false);

  // Notifications
  const [notice, setNotice] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);

  // 1. Initial Load: Fetch Status, Profile, and Cached Master Data (Non-blocking)
  const fetchStatusAndProfile = async (forceRefresh = false) => {
    try {
      if (forceRefresh || !zohoStatus) {
        setIsLoading(true);
      }
      const [statusRes, profileRes] = await Promise.allSettled([
        getZohoStatus(forceRefresh),
        getCurrentUser(),
      ]);

      if (statusRes.status === "fulfilled") {
        setZohoStatus(statusRes.value);
        if (statusRes.value.connected) {
          try {
            const md = await getMasterDataSummary(forceRefresh);
            setMasterData(md);
          } catch (_) {}
        }
      }
      if (profileRes.status === "fulfilled") {
        setUserProfile(profileRes.value);
      }
    } catch (err: any) {
      console.error("Failed to load initial settings:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatusAndProfile(false);

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

    // Check URL parameters for OAuth redirect notices
    const zohoRedirectStatus = searchParams.get("zoho_status");
    const orgName = searchParams.get("org_name");
    const errorDetail = searchParams.get("error_detail");

    if (zohoRedirectStatus === "connected") {
      setNotice({
        type: "success",
        message: `Zoho Books successfully connected${orgName ? ` to ${orgName}` : ""}! Master Chart of Accounts, Tax Rates, and Vendors synchronized.`,
      });
      if (typeof window !== "undefined") {
        window.history.replaceState({}, "", window.location.pathname);
      }
      fetchStatusAndProfile(true);
    } else if (zohoRedirectStatus === "error") {
      setNotice({
        type: "error",
        message: `Zoho OAuth Connection failed: ${errorDetail || "Authorization was denied or expired."}`,
      });
      if (typeof window !== "undefined") {
        window.history.replaceState({}, "", window.location.pathname);
      }
    }

    return () => {
      window.removeEventListener("zoho-status-updated", handleStatusUpdate);
    };
  }, []);

  // Derived connection state
  const computedState: ZohoConnectionState = isConnecting
    ? "CONNECTING"
    : isSyncing
    ? "SYNCING"
    : !zohoStatus?.connected
    ? "DISCONNECTED"
    : !zohoStatus.organization_id
    ? "ORGANIZATION_REQUIRED"
    : zohoStatus.error_message
    ? "ERROR"
    : "CONNECTED";

  // 2. Connect Handler (Calls GET /api/v1/zoho/connect and navigates browser)
  const handleConnectZoho = async () => {
    try {
      setIsConnecting(true);
      setNotice(null);
      const res = await getZohoConnectUrl(selectedAccountsUrl, customRedirectUri);
      const authUrl = res.auth_url || res.authorization_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        throw new Error("Authorization URL was not returned by the server.");
      }
    } catch (err: any) {
      setNotice({
        type: "error",
        message: err.message || "Failed to initiate Zoho connection.",
      });
      setIsConnecting(false);
    }
  };

  // 3. Sync Handler (Calls POST /api/v1/zoho/sync)
  const handleSyncNow = async () => {
    try {
      setIsSyncing(true);
      setNotice(null);
      const res = await triggerZohoSync();
      const coaCount = res.accounts_synced ?? res.chart_of_accounts ?? 0;
      const taxCount = res.taxes_synced ?? res.tax_rates ?? 0;
      const vendorCount = res.vendors_synced ?? res.vendors ?? 0;
      setNotice({
        type: "success",
        message: `Master data synchronized! ${coaCount} COA accounts, ${taxCount} tax rates, and ${vendorCount} vendors updated.`,
      });
    } catch (err: any) {
      setNotice({
        type: "error",
        message: err.message || "Failed to sync Zoho master data.",
      });
    } finally {
      setIsSyncing(false);
    }
  };

  // 4. Open Organization Modal (Calls GET /api/v1/zoho/organizations)
  const handleOpenOrgModal = async () => {
    try {
      setIsSelectingOrg(true);
      const res = await getZohoOrganizations();
      const orgs = Array.isArray(res) ? res : ((res as any).organizations || []);
      setOrganizations(orgs);
      setShowOrgModal(true);
    } catch (err: any) {
      setNotice({
        type: "error",
        message: err.message || "Failed to list accessible Zoho organizations.",
      });
    } finally {
      setIsSelectingOrg(false);
    }
  };

  // 5. Select Organization (Calls POST /api/v1/zoho/select-org)
  const handleSelectOrganization = async (orgId: string, orgName: string) => {
    try {
      setIsSelectingOrg(true);
      const res = await selectZohoOrganization(orgId, orgName);
      setShowOrgModal(false);
      await fetchStatusAndProfile();
      setNotice({
        type: "success",
        message: `Active organization set to "${orgName}". Synced ${res.accounts_synced ?? 0} accounts, ${res.taxes_synced ?? 0} taxes, and ${res.vendors_synced ?? 0} vendors.`,
      });
    } catch (err: any) {
      setNotice({
        type: "error",
        message: err.message || "Failed to select organization.",
      });
    } finally {
      setIsSelectingOrg(false);
    }
  };

  // 6. Disconnect Handler (Calls POST /api/v1/zoho/disconnect)
  const handleConfirmDisconnect = async () => {
    try {
      setIsDisconnecting(true);
      await disconnectZoho();
      setShowDisconnectModal(false);
      setMasterData(null);
      await fetchStatusAndProfile();
      setNotice({
        type: "info",
        message: "Zoho Books integration disconnected successfully.",
      });
    } catch (err: any) {
      setNotice({
        type: "error",
        message: err.message || "Failed to disconnect Zoho Books.",
      });
    } finally {
      setIsDisconnecting(false);
    }
  };

  // 7. Role Switching (Dev utility for testing RBAC)
  const handleRoleChange = async (role: "ADMIN" | "FINANCE" | "VIEWER") => {
    try {
      setIsSwitchingRole(true);
      await switchDevRole(role);
      await fetchStatusAndProfile();
      setNotice({
        type: "info",
        message: `Switched active role to ${role}.`,
      });
    } catch (err: any) {
      setNotice({
        type: "error",
        message: "Failed to switch role.",
      });
    } finally {
      setIsSwitchingRole(false);
    }
  };

  const isViewer = userProfile?.role === "VIEWER";

  // Filtered lists for master data tabs
  const filteredAccounts = (masterData?.accounts || masterData?.chart_of_accounts || []).filter(
    (a: any) =>
      (a.account_name || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (a.account_code && a.account_code.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (a.account_type || "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredTaxes = (masterData?.taxes || masterData?.tax_rates || []).filter(
    (t: any) =>
      (t.tax_name || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (t.tax_type || "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredVendors = (masterData?.vendors || []).filter(
    (v: any) =>
      (v.vendor_name || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (v.gstin && v.gstin.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (v.pan && v.pan.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="container" style={{ padding: "32px 0 64px" }}>
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "28px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
            <Building2 size={24} color="var(--accent)" />
            <h1 style={{ fontSize: "24px", fontWeight: "700", letterSpacing: "-0.03em" }}>
              Zoho Books Integration & Settings
            </h1>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
            Manage OAuth2 connection, live Chart of Accounts synchronization, and organization scoping.
          </p>
        </div>

        {/* RBAC Role Pill & Dev Switcher */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: "8px",
            background: "#ffffff",
            padding: "10px 14px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-subtle)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}>
            <UserCheck size={14} color="var(--text-secondary)" />
            <span style={{ color: "var(--text-secondary)" }}>Authenticated:</span>
            <strong>{userProfile?.email || "finance@sakshi.ai"}</strong>
            <span
              className={`badge ${
                userProfile?.role === "ADMIN"
                  ? "badge-success"
                  : userProfile?.role === "FINANCE"
                  ? "badge-uploaded"
                  : "badge-danger"
              }`}
              style={{ fontSize: "11px", fontWeight: "600" }}
            >
              {userProfile?.role || "FINANCE"}
            </span>
          </div>

          {/* Dev Role Testing Controls */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px" }}>
            <span style={{ color: "var(--text-tertiary)" }}>Test Role:</span>
            {(["ADMIN", "FINANCE", "VIEWER"] as const).map((r) => (
              <button
                key={r}
                onClick={() => handleRoleChange(r)}
                disabled={isSwitchingRole || userProfile?.role === r}
                style={{
                  padding: "2px 6px",
                  borderRadius: "4px",
                  fontSize: "10px",
                  fontWeight: userProfile?.role === r ? "700" : "500",
                  background: userProfile?.role === r ? "var(--border-strong)" : "var(--bg-main)",
                  color: userProfile?.role === r ? "#000" : "var(--text-secondary)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Global Notifications */}
      {notice && (
        <div
          style={{
            padding: "14px 18px",
            borderRadius: "var(--radius-md)",
            marginBottom: "24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background:
              notice.type === "success"
                ? "var(--success-bg)"
                : notice.type === "error"
                ? "var(--danger-bg)"
                : "var(--bg-main)",
            border: `1px solid ${
              notice.type === "success"
                ? "var(--success)"
                : notice.type === "error"
                ? "var(--danger)"
                : "var(--border-strong)"
            }`,
            color:
              notice.type === "success"
                ? "#1e7e34"
                : notice.type === "error"
                ? "var(--danger)"
                : "var(--text-primary)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {notice.type === "success" && <CheckCircle2 size={18} />}
            {notice.type === "error" && <XCircle size={18} />}
            {notice.type === "info" && <Info size={18} />}
            <span style={{ fontSize: "13px", fontWeight: "500" }}>{notice.message}</span>
          </div>
          <button
            onClick={() => setNotice(null)}
            style={{ fontSize: "12px", color: "inherit", fontWeight: "600", padding: "2px 8px" }}
          >
            ✕
          </button>
        </div>
      )}

      {/* RBAC Viewer Warning */}
      {isViewer && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "var(--radius-md)",
            marginBottom: "20px",
            background: "var(--warning-bg)",
            border: "1px solid var(--warning)",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            color: "#995a00",
            fontSize: "13px",
          }}
        >
          <AlertTriangle size={16} />
          <span>
            <strong>Read-Only Mode:</strong> You are logged in with the <strong>VIEWER</strong> role. Zoho OAuth connection, organization switching, synchronization, and disconnection actions are restricted to <strong>ADMIN</strong> and <strong>FINANCE</strong> roles.
          </span>
        </div>
      )}

      {/* MAIN CONNECTION STATUS CARD */}
      <div className="card" style={{ padding: "28px", marginBottom: "28px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: "1px solid var(--border-subtle)",
            paddingBottom: "20px",
            marginBottom: "24px",
            flexWrap: "wrap",
            gap: "16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "12px",
                background:
                  computedState === "CONNECTED"
                    ? "var(--success-bg)"
                    : computedState === "ORGANIZATION_REQUIRED"
                    ? "var(--warning-bg)"
                    : "var(--bg-main)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: `1px solid ${
                  computedState === "CONNECTED"
                    ? "var(--success)"
                    : computedState === "ORGANIZATION_REQUIRED"
                    ? "var(--warning)"
                    : "var(--border-subtle)"
                }`,
              }}
            >
              <Link2
                size={24}
                color={
                  computedState === "CONNECTED"
                    ? "var(--success)"
                    : computedState === "ORGANIZATION_REQUIRED"
                    ? "var(--warning)"
                    : "var(--text-tertiary)"
                }
              />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <h2 style={{ fontSize: "19px", fontWeight: "700" }}>Zoho Books</h2>
                {isLoading ? (
                  <span className="badge badge-uploaded" style={{ fontSize: "11px" }}>Loading...</span>
                ) : computedState === "CONNECTED" ? (
                  <span className="badge badge-success" style={{ fontSize: "11px", fontWeight: "600" }}>
                    Connected ✓
                  </span>
                ) : computedState === "ORGANIZATION_REQUIRED" ? (
                  <span className="badge badge-warning" style={{ fontSize: "11px", fontWeight: "600" }}>
                    Organization Selection Required
                  </span>
                ) : computedState === "SYNCING" ? (
                  <span className="badge badge-uploaded" style={{ fontSize: "11px", fontWeight: "600" }}>
                    Syncing...
                  </span>
                ) : (
                  <span className="badge badge-danger" style={{ fontSize: "11px", fontWeight: "600" }}>
                    Not Connected
                  </span>
                )}
              </div>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "3px" }}>
                {computedState === "CONNECTED"
                  ? `Active connection to ${zohoStatus?.organization_name || "Zoho Books"}`
                  : computedState === "ORGANIZATION_REQUIRED"
                  ? "OAuth authorized. Please select your active Zoho organization below."
                  : "Connect your Zoho Books organization to enable live COA mapping and direct Bill export."}
              </p>
            </div>
          </div>

          {/* Top Quick Actions */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {zohoStatus?.connected ? (
              <>
                <button
                  type="button"
                  onClick={handleSyncNow}
                  disabled={isSyncing || isViewer}
                  className="btn btn-secondary"
                  style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}
                  title={isViewer ? "Viewer cannot sync" : "Sync live Chart of Accounts, Taxes & Vendors"}
                >
                  <RefreshCw size={14} className={isSyncing ? "animate-spin" : ""} />
                  <span>{isSyncing ? "Syncing..." : "Sync Master Data"}</span>
                </button>
                <button
                  type="button"
                  onClick={handleOpenOrgModal}
                  disabled={isSelectingOrg || isViewer}
                  className="btn btn-secondary"
                  style={{ fontSize: "13px" }}
                  title={isViewer ? "Viewer cannot switch organization" : "View or switch organization"}
                >
                  Switch Org
                </button>
                <button
                  type="button"
                  onClick={() => setShowDisconnectModal(true)}
                  disabled={isDisconnecting || isViewer}
                  className="btn btn-danger"
                  style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}
                  title={isViewer ? "Viewer cannot disconnect" : "Disconnect integration"}
                >
                  <Unlink size={14} />
                  <span>Disconnect</span>
                </button>
              </>
            ) : null}
          </div>
        </div>

        {/* ORGANIZATION REQUIRED ALERT */}
        {computedState === "ORGANIZATION_REQUIRED" && (
          <div
            style={{
              padding: "16px 20px",
              background: "var(--warning-bg)",
              border: "1px solid var(--warning)",
              borderRadius: "var(--radius-md)",
              marginBottom: "24px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <div style={{ fontWeight: "700", fontSize: "14px", color: "#995a00", marginBottom: "2px" }}>
                Select Active Zoho Organization
              </div>
              <p style={{ fontSize: "13px", color: "#7a4800" }}>
                Your account is connected to Zoho, but an organization has not been selected yet.
              </p>
            </div>
            <button
              onClick={handleOpenOrgModal}
              disabled={isViewer}
              className="btn btn-primary"
              style={{ fontSize: "13px", padding: "8px 16px" }}
            >
              Select Organization Now
            </button>
          </div>
        )}

        {/* CONNECTION STATE BODY */}
        {isLoading ? (
          <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-secondary)" }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 12px" }} />
            <p style={{ fontSize: "14px" }}>Checking Zoho Books connection state...</p>
          </div>
        ) : zohoStatus?.connected ? (
          /* CONNECTED METRICS DASHBOARD */
          <div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
                gap: "16px",
                marginBottom: "24px",
              }}
            >
              {/* Organization Card */}
              <div
                style={{
                  background: "var(--bg-main)",
                  padding: "16px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-secondary)", fontSize: "12px", marginBottom: "6px" }}>
                  <Building2 size={14} />
                  <span>Organization</span>
                </div>
                <div style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-primary)" }}>
                  {zohoStatus.organization_name || "Default Organization"}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
                  ID: <code>{zohoStatus.organization_id || "Auto-Selected"}</code>
                </div>
              </div>

              {/* Data Center / API Domain Card */}
              <div
                style={{
                  background: "var(--bg-main)",
                  padding: "16px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-secondary)", fontSize: "12px", marginBottom: "6px" }}>
                  <Globe size={14} />
                  <span>Data Center API Domain</span>
                </div>
                <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-primary)" }}>
                  {zohoStatus.api_domain || "https://www.zohoapis.in"}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
                  OAuth2 Token: Encrypted at Rest
                </div>
              </div>

              {/* Chart of Accounts Count */}
              <div
                style={{
                  background: "var(--bg-main)",
                  padding: "16px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-secondary)", fontSize: "12px", marginBottom: "6px" }}>
                  <Layers size={14} />
                  <span>COA Accounts</span>
                </div>
                <div style={{ fontSize: "22px", fontWeight: "800", color: "var(--accent)" }}>
                  {zohoStatus.accounts_count}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                  Live Accounts Fed to AI Engine
                </div>
              </div>

              {/* Tax Rates Count */}
              <div
                style={{
                  background: "var(--bg-main)",
                  padding: "16px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-secondary)", fontSize: "12px", marginBottom: "6px" }}>
                  <Percent size={14} />
                  <span>Tax Rates</span>
                </div>
                <div style={{ fontSize: "22px", fontWeight: "800", color: "var(--success)" }}>
                  {zohoStatus.taxes_count}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                  Available GST / Tax Rates
                </div>
              </div>

              {/* Vendors Count */}
              <div
                style={{
                  background: "var(--bg-main)",
                  padding: "16px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-secondary)", fontSize: "12px", marginBottom: "6px" }}>
                  <Users size={14} />
                  <span>Vendors / Contacts</span>
                </div>
                <div style={{ fontSize: "22px", fontWeight: "800", color: "#6f42c1" }}>
                  {zohoStatus.vendors_count || 0}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                  Synced Contacts from Zoho
                </div>
              </div>
            </div>

            {/* Sync Timestamp and Security Metadata */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "12px 16px",
                background: "#f9f9fb",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-subtle)",
                fontSize: "12px",
                color: "var(--text-secondary)",
                flexWrap: "wrap",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Calendar size={14} />
                <span>Last Master Data Sync: </span>
                <strong>
                  {zohoStatus.last_sync_at
                    ? new Date(zohoStatus.last_sync_at).toLocaleString()
                    : "Active"}
                </strong>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <ShieldCheck size={14} color="var(--success)" />
                <span>Tokens Encrypted at Rest (AES-256 / Fernet)</span>
              </div>
            </div>
          </div>
        ) : (
          /* DISCONNECTED STATE */
          <div style={{ padding: "12px 0" }}>
            <div
              style={{
                background: "#f9f9fb",
                padding: "28px",
                borderRadius: "var(--radius-md)",
                border: "1px dashed var(--border-strong)",
                marginBottom: "24px",
              }}
            >
              <h3 style={{ fontSize: "16px", fontWeight: "700", marginBottom: "8px" }}>
                Connect Zoho Books Sandbox / Production
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.6", marginBottom: "20px" }}>
                Connecting Zoho Books enables real-time synchronization of your Chart of Accounts, GST tax rates, and Vendor contacts into the Qwen3-4B accounting categorization engine, and unlocks 1-click double-entry bill export with original document attachments.
              </p>

              {/* Data Center Selection */}
              <div style={{ maxWidth: "540px", marginBottom: "18px" }}>
                <label className="form-label" style={{ fontSize: "12px", fontWeight: "600" }}>
                  Zoho Account Data Center Domain
                </label>
                <select
                  className="form-input"
                  value={selectedAccountsUrl}
                  onChange={(e) => setSelectedAccountsUrl(e.target.value)}
                  style={{ fontSize: "13px" }}
                  disabled={isConnecting || isViewer}
                >
                  {DATA_CENTERS.map((dc) => (
                    <option key={dc.id} value={dc.url}>
                      {dc.label} ({dc.url})
                    </option>
                  ))}
                </select>
                <span style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px", display: "block" }}>
                  Choose the region where your Zoho Books organization was created.
                </span>
              </div>

              {/* Redirect URI Configuration and Copy Helper */}
              <div style={{ maxWidth: "540px", marginBottom: "24px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <label className="form-label" style={{ fontSize: "12px", fontWeight: "600", margin: 0 }}>
                    Authorized OAuth Redirect URI
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      if (typeof navigator !== "undefined" && navigator.clipboard) {
                        navigator.clipboard.writeText(customRedirectUri);
                        setCopiedUri(true);
                        setTimeout(() => setCopiedUri(false), 2500);
                      }
                    }}
                    style={{
                      fontSize: "11px",
                      color: "var(--accent)",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: "2px 6px",
                      borderRadius: "4px",
                    }}
                  >
                    {copiedUri ? <Check size={12} color="var(--success)" /> : <Copy size={12} />}
                    <span style={{ fontWeight: copiedUri ? "700" : "500", color: copiedUri ? "var(--success)" : "var(--accent)" }}>
                      {copiedUri ? "Copied!" : "Copy URI"}
                    </span>
                  </button>
                </div>
                <input
                  type="text"
                  className="form-input"
                  value={customRedirectUri}
                  onChange={(e) => setCustomRedirectUri(e.target.value)}
                  style={{ fontSize: "13px", fontFamily: "monospace", background: "#ffffff" }}
                  disabled={isConnecting || isViewer}
                  placeholder="http://localhost:8000/api/v1/zoho/callback"
                />
                <div
                  style={{
                    fontSize: "11px",
                    color: "#856404",
                    background: "#fff8eb",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    marginTop: "6px",
                    border: "1px solid #ffe8cc",
                    lineHeight: "1.45",
                  }}
                >
                  <strong>⚠️ Zoho Console Configuration:</strong> The Authorized Redirect URI registered in your{" "}
                  <a
                    href="https://api-console.zoho.in"
                    target="_blank"
                    rel="noreferrer"
                    style={{ textDecoration: "underline", fontWeight: "600", color: "#0066cc" }}
                  >
                    Zoho API Console
                  </a>{" "}
                  for Client ID <code>1000.TJIHZ9PMJNK8KGU4BV7LUUREFZ9O7E</code> must <strong>EXACTLY</strong> match this URI.
                </div>
              </div>

              {/* Connect Button */}
              <button
                type="button"
                onClick={handleConnectZoho}
                disabled={isConnecting || isViewer}
                className="btn btn-primary"
                style={{
                  padding: "10px 24px",
                  fontSize: "14px",
                  fontWeight: "600",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Link2 size={16} className={isConnecting ? "animate-spin" : ""} />
                <span>{isConnecting ? "Connecting to Zoho..." : "Connect Zoho Books"}</span>
                <ArrowRight size={14} />
              </button>
            </div>

            {/* Feature preview checklist */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" }}>
              <div style={{ padding: "16px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", background: "#ffffff" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: "600", fontSize: "13px", marginBottom: "4px" }}>
                  <Check size={14} color="var(--success)" />
                  <span>Live Chart of Accounts</span>
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  Qwen3-4B directly categorizes invoice items against your real Zoho ledger accounts.
                </p>
              </div>

              <div style={{ padding: "16px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", background: "#ffffff" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: "600", fontSize: "13px", marginBottom: "4px" }}>
                  <Check size={14} color="var(--success)" />
                  <span>GST & TDS Tax Rates</span>
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  Automatic mapping of CGST, SGST, IGST tax IDs and TDS withholding categories.
                </p>
              </div>

              <div style={{ padding: "16px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", background: "#ffffff" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: "600", fontSize: "13px", marginBottom: "4px" }}>
                  <Check size={14} color="var(--success)" />
                  <span>Idempotent Bill Export</span>
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  Atomic bill creation with original PDF/image attachment and timeout reconciliation.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SYNCHRONIZED MASTER DATA INSPECTION TABS */}
      {zohoStatus?.connected && (
        <div className="card" style={{ padding: "24px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "1px solid var(--border-subtle)",
              paddingBottom: "16px",
              marginBottom: "20px",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            {/* Tabs */}
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                type="button"
                onClick={() => setActiveTab("overview")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                  fontWeight: activeTab === "overview" ? "700" : "500",
                  background: activeTab === "overview" ? "var(--accent)" : "transparent",
                  color: activeTab === "overview" ? "#ffffff" : "var(--text-secondary)",
                }}
              >
                Sync Overview
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("coa")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                  fontWeight: activeTab === "coa" ? "700" : "500",
                  background: activeTab === "coa" ? "var(--accent)" : "transparent",
                  color: activeTab === "coa" ? "#ffffff" : "var(--text-secondary)",
                }}
              >
                Chart of Accounts ({masterData?.accounts?.length || masterData?.chart_of_accounts_count || zohoStatus.accounts_count || 0})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("taxes")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                  fontWeight: activeTab === "taxes" ? "700" : "500",
                  background: activeTab === "taxes" ? "var(--accent)" : "transparent",
                  color: activeTab === "taxes" ? "#ffffff" : "var(--text-secondary)",
                }}
              >
                Taxes ({masterData?.taxes?.length || masterData?.tax_rates_count || zohoStatus.taxes_count || 0})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("vendors")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                  fontWeight: activeTab === "vendors" ? "700" : "500",
                  background: activeTab === "vendors" ? "var(--accent)" : "transparent",
                  color: activeTab === "vendors" ? "#ffffff" : "var(--text-secondary)",
                }}
              >
                Vendors ({masterData?.vendors?.length || masterData?.vendors_count || zohoStatus.vendors_count || 0})
              </button>
            </div>

            {/* Search Input for Tables */}
            {activeTab !== "overview" && (
              <div style={{ position: "relative", minWidth: "220px" }}>
                <Search size={14} style={{ position: "absolute", left: "10px", top: "10px", color: "var(--text-tertiary)" }} />
                <input
                  type="text"
                  placeholder={`Search ${activeTab}...`}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="form-input"
                  style={{ paddingLeft: "30px", fontSize: "12px", height: "34px" }}
                />
              </div>
            )}
          </div>

          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "16px" }}>
                Master data is cached locally in PostgreSQL to ensure ultra-low latency during AI invoice categorization and offline-resilient finance verification.
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "16px" }}>
                <div style={{ padding: "16px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontWeight: "700", fontSize: "14px", marginBottom: "4px" }}>Chart of Accounts Engine</div>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                    Synchronized ledger accounts are mapped directly to invoice line descriptions by Qwen3-4B. The user can review, override, and approve the account before journal creation.
                  </p>
                </div>
                <div style={{ padding: "16px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontWeight: "700", fontSize: "14px", marginBottom: "4px" }}>Indian GST Tax Sync</div>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                    CGST, SGST, IGST tax percentages and tax identifiers are pulled directly from Zoho Books settings to compute tax breakdowns accurately.
                  </p>
                </div>
                <div style={{ padding: "16px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontWeight: "700", fontSize: "14px", marginBottom: "4px" }}>Vendor Contact Reconciliation</div>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                    Vendor profiles with GSTIN, PAN, and Zoho Contact IDs are used for duplicate matching and vendor mapping during bill export.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CHART OF ACCOUNTS TABLE */}
          {activeTab === "coa" && (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid var(--border-subtle)", textAlign: "left", color: "var(--text-secondary)" }}>
                    <th style={{ padding: "8px 12px" }}>Account Name</th>
                    <th style={{ padding: "8px 12px" }}>Zoho Account ID</th>
                    <th style={{ padding: "8px 12px" }}>Code</th>
                    <th style={{ padding: "8px 12px" }}>Type</th>
                    <th style={{ padding: "8px 12px" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAccounts.length > 0 ? (
                    filteredAccounts.map((acc) => (
                      <tr key={acc.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "10px 12px", fontWeight: "600" }}>{acc.account_name}</td>
                        <td style={{ padding: "10px 12px" }}><code>{acc.zoho_account_id}</code></td>
                        <td style={{ padding: "10px 12px", color: "var(--text-secondary)" }}>{acc.account_code || "—"}</td>
                        <td style={{ padding: "10px 12px" }}>
                          <span className="badge badge-uploaded" style={{ fontSize: "11px" }}>{acc.account_type}</span>
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          <span className={`badge ${acc.is_active ? "badge-success" : "badge-danger"}`} style={{ fontSize: "10px" }}>
                            {acc.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} style={{ padding: "24px", textAlign: "center", color: "var(--text-tertiary)" }}>
                        No accounts found matching search term.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 3: TAXES TABLE */}
          {activeTab === "taxes" && (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid var(--border-subtle)", textAlign: "left", color: "var(--text-secondary)" }}>
                    <th style={{ padding: "8px 12px" }}>Tax Name</th>
                    <th style={{ padding: "8px 12px" }}>Zoho Tax ID</th>
                    <th style={{ padding: "8px 12px" }}>Rate %</th>
                    <th style={{ padding: "8px 12px" }}>Type</th>
                    <th style={{ padding: "8px 12px" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTaxes.length > 0 ? (
                    filteredTaxes.map((tax) => (
                      <tr key={tax.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "10px 12px", fontWeight: "600" }}>{tax.tax_name}</td>
                        <td style={{ padding: "10px 12px" }}><code>{tax.zoho_tax_id}</code></td>
                        <td style={{ padding: "10px 12px", fontWeight: "700", color: "var(--success)" }}>{tax.tax_percentage}%</td>
                        <td style={{ padding: "10px 12px" }}>
                          <span className="badge badge-uploaded" style={{ fontSize: "11px" }}>{tax.tax_type}</span>
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          <span className={`badge ${tax.is_active ? "badge-success" : "badge-danger"}`} style={{ fontSize: "10px" }}>
                            {tax.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} style={{ padding: "24px", textAlign: "center", color: "var(--text-tertiary)" }}>
                        No tax rates found matching search term.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 4: VENDORS TABLE */}
          {activeTab === "vendors" && (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid var(--border-subtle)", textAlign: "left", color: "var(--text-secondary)" }}>
                    <th style={{ padding: "8px 12px" }}>Vendor Name</th>
                    <th style={{ padding: "8px 12px" }}>Zoho Contact ID</th>
                    <th style={{ padding: "8px 12px" }}>GSTIN</th>
                    <th style={{ padding: "8px 12px" }}>PAN</th>
                    <th style={{ padding: "8px 12px" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredVendors.length > 0 ? (
                    filteredVendors.map((v) => (
                      <tr key={v.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "10px 12px", fontWeight: "600" }}>{v.vendor_name}</td>
                        <td style={{ padding: "10px 12px" }}><code>{v.zoho_contact_id || "—"}</code></td>
                        <td style={{ padding: "10px 12px" }}>{v.gstin ? <code>{v.gstin}</code> : "—"}</td>
                        <td style={{ padding: "10px 12px" }}>{v.pan ? <code>{v.pan}</code> : "—"}</td>
                        <td style={{ padding: "10px 12px" }}>
                          <span className="badge badge-success" style={{ fontSize: "10px" }}>
                            {v.approval_status}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} style={{ padding: "24px", textAlign: "center", color: "var(--text-tertiary)" }}>
                        No vendors found in local cache. Click &quot;Sync Master Data&quot; to fetch contacts.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ORGANIZATION SELECTION MODAL */}
      {showOrgModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "520px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: "700" }}>Select Zoho Organization</h3>
              <button onClick={() => setShowOrgModal(false)} style={{ fontSize: "16px", color: "var(--text-tertiary)" }}>
                ✕
              </button>
            </div>

            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "16px" }}>
              Choose the Zoho Books organization to bind with this tenant:
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "20px", maxHeight: "300px", overflowY: "auto" }}>
              {organizations && organizations.length > 0 ? (
                organizations.map((org) => {
                  const isCurrent = org.organization_id === zohoStatus?.organization_id;
                  return (
                    <div
                      key={org.organization_id}
                      onClick={() => handleSelectOrganization(org.organization_id, org.name)}
                      style={{
                        padding: "12px 16px",
                        borderRadius: "var(--radius-sm)",
                        border: `1px solid ${isCurrent ? "var(--accent)" : "var(--border-subtle)"}`,
                        background: isCurrent ? "#f0f7ff" : "#ffffff",
                        cursor: "pointer",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: "600", fontSize: "14px" }}>{org.name}</div>
                        <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                          ID: {org.organization_id} {org.currency_code ? `• ${org.currency_code}` : ""}
                        </div>
                      </div>
                      {isCurrent ? (
                        <span className="badge badge-success" style={{ fontSize: "11px" }}>Active</span>
                      ) : (
                        <ChevronRight size={16} color="var(--text-tertiary)" />
                      )}
                    </div>
                  );
                })
              ) : (
                <p style={{ fontSize: "13px", color: "var(--text-secondary)", textAlign: "center", padding: "16px" }}>
                  No organizations found on this Zoho account.
                </p>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setShowOrgModal(false)}
                className="btn btn-secondary"
                style={{ padding: "6px 14px", fontSize: "13px" }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DISCONNECT CONFIRMATION MODAL */}
      {showDisconnectModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "440px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px", color: "var(--danger)" }}>
              <AlertTriangle size={20} />
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-primary)" }}>
                Disconnect Zoho Books?
              </h3>
            </div>

            <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "20px" }}>
              Are you sure you want to disconnect Zoho Books? Stored OAuth tokens will be securely removed. You will need to re-authenticate to sync accounts or export bills.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setShowDisconnectModal(false)}
                disabled={isDisconnecting}
                className="btn btn-secondary"
                style={{ padding: "6px 14px", fontSize: "13px" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDisconnect}
                disabled={isDisconnecting}
                className="btn btn-danger"
                style={{ padding: "6px 14px", fontSize: "13px" }}
              >
                {isDisconnecting ? "Disconnecting..." : "Confirm Disconnect"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="container" style={{ padding: "40px 0" }}>Loading settings...</div>}>
      <SettingsContent />
    </Suspense>
  );
}
