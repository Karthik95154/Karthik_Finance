"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Inbox,
  FileSpreadsheet,
  FileCheck,
  Layers,
  UploadCloud,
  ShieldCheck,
  Menu,
  X,
  LogOut,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  Activity,
  AlertTriangle,
  XCircle,
} from "lucide-react";
import { getHealth, HealthResponse, getCurrentUser, UserProfile } from "@/lib/api";
import SystemStatusModal, { getStatusBadge } from "./SystemStatusModal";

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  hideHealthBadge?: boolean;
}

export default function AppShell({
  children,
  title,
  subtitle,
  actions,
  hideHealthBadge,
}: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [statusModalOpen, setStatusModalOpen] = useState(false);
  const [isRefreshingHealth, setIsRefreshingHealth] = useState(false);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [logoutModalOpen, setLogoutModalOpen] = useState(false);

  const handleLogoutConfirm = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("dev_auth_token");
      localStorage.removeItem("user_info");
      window.location.href = "/";
    }
  };

  const fetchHealth = async () => {
    try {
      setIsRefreshingHealth(true);
      const data = await getHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setIsRefreshingHealth(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Check localStorage user_info or fetch from API /auth/me
    if (typeof window !== "undefined") {
      const savedUser = localStorage.getItem("user_info");
      if (savedUser) {
        try {
          setUserProfile(JSON.parse(savedUser));
        } catch {}
      }
    }
    getCurrentUser()
      .then((u) => {
        if (u) {
          setUserProfile(u);
          if (typeof window !== "undefined") {
            localStorage.setItem("user_info", JSON.stringify(u));
          }
        }
      })
      .catch(() => null);
  }, []);

  const navItems = [
    {
      label: "Dashboard",
      href: "/dashboard",
      icon: LayoutDashboard,
      active: pathname === "/dashboard",
    },
    {
      label: "Inbox",
      href: "/inbox",
      icon: Inbox,
      active: pathname === "/inbox",
      badge: "Stage 7",
    },
    {
      label: "Invoices",
      href: "/finance/invoices",
      icon: FileSpreadsheet,
      active:
        pathname.startsWith("/finance/invoices") &&
        !pathname.includes("/processing") &&
        pathname !== "/finance/settings",
    },
    {
      label: "Integrations",
      href: "/integrations",
      icon: Layers,
      active: pathname === "/integrations" || pathname === "/finance/settings",
      badge: "Stage 8",
    },
  ];

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        background: "var(--bg-main)",
        color: "var(--text-primary)",
      }}
    >
      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.4)",
            zIndex: 140,
            backdropFilter: "blur(4px)",
          }}
        />
      )}

      {/* Persistent Sidebar */}
      <aside
        style={{
          width: "260px",
          background: "#ffffff",
          borderRight: "1px solid var(--border-subtle)",
          display: "flex",
          flexDirection: "column",
          position: "fixed",
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 150,
          transition: "transform 0.25s ease",
          transform: mobileOpen ? "translateX(0)" : undefined,
        }}
        className={`app-sidebar ${mobileOpen ? "open" : ""}`}
      >
        {/* Brand Header */}
        <div
          style={{
            padding: "20px 20px 16px",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Link
            href="/dashboard"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              textDecoration: "none",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                boxShadow: "0 2px 8px rgba(0, 113, 227, 0.25)",
              }}
            >
              <ShieldCheck size={18} />
            </div>
            <div>
              <div
                style={{
                  fontSize: "16px",
                  fontWeight: "700",
                  letterSpacing: "-0.02em",
                  color: "var(--text-primary)",
                  lineHeight: "1.2",
                }}
              >
                Finance Module
              </div>
              <div
                style={{
                  fontSize: "11px",
                  color: "var(--text-secondary)",
                  fontWeight: "500",
                }}
              >
                Autonomous AP
              </div>
            </div>
          </Link>

          {/* Close for mobile */}
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            style={{
              display: "none",
              color: "var(--text-secondary)",
              padding: "4px",
            }}
            className="mobile-close-btn"
          >
            <X size={18} />
          </button>
        </div>

        {/* Primary Action Button */}
        <div style={{ padding: "16px 16px 8px" }}>
          <Link
            href="/finance/upload"
            className="btn btn-primary"
            style={{
              width: "100%",
              padding: "9px 14px",
              fontSize: "13px",
              fontWeight: "600",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              borderRadius: "var(--radius-sm)",
              boxShadow: "0 2px 6px rgba(0, 113, 227, 0.2)",
            }}
          >
            <UploadCloud size={16} />
            <span>Upload Invoice</span>
          </Link>
        </div>

        {/* Navigation List */}
        <div style={{ padding: "8px 12px", flex: 1, overflowY: "auto" }}>
          <div
            style={{
              fontSize: "11px",
              fontWeight: "700",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--text-tertiary)",
              padding: "8px 10px 4px",
            }}
          >
            Workflows
          </div>
          <nav style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "9px 12px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "13px",
                    fontWeight: item.active ? "600" : "500",
                    color: item.active ? "var(--accent)" : "var(--text-primary)",
                    background: item.active ? "rgba(0, 113, 227, 0.08)" : "transparent",
                    transition: "all 0.15s ease",
                    textDecoration: "none",
                  }}
                  className="nav-item-link"
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <Icon
                      size={17}
                      color={item.active ? "var(--accent)" : "var(--text-secondary)"}
                    />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: "600",
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: "var(--border-subtle)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer: System Status & User */}
        <div
          style={{
            padding: "16px",
            borderTop: "1px solid var(--border-subtle)",
            background: "#fafafa",
          }}
        >
          {/* Interactive Health Pill */}
          {(() => {
            const has404 = health?.colab_vlm?.includes("404") || health?.colab_accounting?.includes("404");
            const isOk = health?.status === "ok" || health?.status === "healthy";
            const badge = getStatusBadge(
              isOk ? "online" : has404 ? "404_error" : health?.status || "offline",
              isOk ? 200 : has404 ? 404 : undefined
            );
            const BadgeIcon = badge.icon;
            return (
              <button
                type="button"
                onClick={() => setStatusModalOpen(true)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  fontSize: "11px",
                  color: badge.text,
                  marginBottom: "12px",
                  padding: "7px 10px",
                  background: badge.bg,
                  borderRadius: "6px",
                  border: `1px solid ${badge.border}`,
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.15s ease",
                }}
                title="Click to view full System & AI Engine Diagnostics"
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span
                    style={{
                      width: "7px",
                      height: "7px",
                      borderRadius: "50%",
                      backgroundColor: badge.dot,
                      boxShadow: `0 0 0 2px ${badge.border}`,
                    }}
                  />
                  <span style={{ fontWeight: "600" }}>
                    {isOk ? "System: 200 OK" : has404 ? "AI Engine: 404 Error" : health?.status === "degraded" ? "System: Degraded" : "System: Offline"}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: "600",
                    background: "#ffffff",
                    padding: "1px 5px",
                    borderRadius: "3px",
                    border: `1px solid ${badge.border}`,
                  }}
                >
                  Diagnostics
                </span>
              </button>
            );
          })()}

          {/* User / Sign out */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "6px 4px 0",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {(() => {
                const displayName = userProfile?.full_name || userProfile?.email || "Finance Admin";
                const displaySub = userProfile?.email && userProfile?.full_name ? userProfile.email : (userProfile?.role ? `${userProfile.role} Specialist` : "Review Specialist");
                const parts = displayName.split(" ").filter(Boolean);
                const initials = parts.length >= 2 
                  ? `${parts[0][0]}${parts[1][0]}`.toUpperCase()
                  : displayName.slice(0, 2).toUpperCase();
                return (
                  <>
                    <div
                      style={{
                        width: "28px",
                        height: "28px",
                        borderRadius: "50%",
                        background: "var(--accent-primary, #2563eb)",
                        color: "#ffffff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "11px",
                        fontWeight: "700",
                        flexShrink: 0,
                      }}
                      title={userProfile?.email || displayName}
                    >
                      {initials}
                    </div>
                    <div style={{ fontSize: "12px", lineHeight: "1.2", overflow: "hidden" }}>
                      <div style={{ fontWeight: "600", color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "120px" }} title={displayName}>
                        {displayName}
                      </div>
                      <div style={{ fontSize: "10px", color: "var(--text-tertiary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "120px" }} title={displaySub}>
                        {displaySub}
                      </div>
                    </div>
                  </>
                );
              })()}
            </div>

            <button
              type="button"
              onClick={() => setLogoutModalOpen(true)}
              title="Sign Out"
              style={{
                color: "var(--text-secondary)",
                padding: "6px",
                borderRadius: "4px",
                display: "flex",
                alignItems: "center",
                background: "transparent",
                border: "none",
                cursor: "pointer",
              }}
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div
        style={{
          flex: 1,
          marginLeft: "260px",
          display: "flex",
          flexDirection: "column",
          minHeight: "100vh",
          background: "var(--bg-main)",
        }}
        className="app-main-content"
      >
        {/* Top Header Bar */}
        <header
          style={{
            height: "56px",
            background: "#ffffff",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 24px",
            position: "sticky",
            top: 0,
            zIndex: 90,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {/* Mobile Hamburger */}
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              style={{
                display: "none",
                padding: "6px",
                color: "var(--text-primary)",
              }}
              className="mobile-hamburger-btn"
              aria-label="Open sidebar"
            >
              <Menu size={20} />
            </button>

            {/* Breadcrumb / Title */}
            <div>
              <h1
                style={{
                  fontSize: "15px",
                  fontWeight: "700",
                  color: "var(--text-primary)",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <span>{title || "Finance Workspace"}</span>
                {subtitle && (
                  <>
                    <ChevronRight size={14} color="var(--text-tertiary)" />
                    <span style={{ fontWeight: "400", color: "var(--text-secondary)" }}>
                      {subtitle}
                    </span>
                  </>
                )}
              </h1>
            </div>
          </div>

          {/* Right Header Actions */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {/* Live System Status Header Pill */}
            {!hideHealthBadge && (() => {
              const has404 = health?.colab_vlm?.includes("404") || health?.colab_accounting?.includes("404");
              const isOk = health?.status === "ok" || health?.status === "healthy";
              const badge = getStatusBadge(
                isOk ? "online" : has404 ? "404_error" : health?.status || "offline",
                isOk ? 200 : has404 ? 404 : undefined
              );
              const BadgeIcon = badge.icon;
              return (
                <button
                  type="button"
                  onClick={() => setStatusModalOpen(true)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "6px",
                    background: badge.bg,
                    border: `1px solid ${badge.border}`,
                    color: badge.text,
                    fontSize: "12px",
                    fontWeight: "600",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                  title="Click to view live system diagnostics and status codes"
                >
                  <span
                    style={{
                      width: "7px",
                      height: "7px",
                      borderRadius: "50%",
                      backgroundColor: badge.dot,
                    }}
                  />
                  <span>
                    {isOk ? "200 OK Active" : has404 ? "AI Engine: 404" : health?.status === "degraded" ? "Degraded" : "API Offline"}
                  </span>
                  <Activity size={13} style={{ opacity: 0.7 }} />
                </button>
              );
            })()}

            {actions}

            <Link
              href="/finance/upload"
              className="btn btn-secondary"
              style={{
                padding: "5px 12px",
                fontSize: "12px",
                fontWeight: "600",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <UploadCloud size={14} />
              <span>Upload</span>
            </Link>
          </div>
        </header>

        {/* Page Content */}
        <main style={{ flex: 1, padding: "24px" }}>{children}</main>

        {/* Universal System Status Diagnostics Modal */}
        <SystemStatusModal
          isOpen={statusModalOpen}
          onClose={() => setStatusModalOpen(false)}
          health={health}
          loading={isRefreshingHealth}
          onRefresh={fetchHealth}
        />

        {/* Centered Logout Confirmation Modal */}
        {logoutModalOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 9999,
              background: "rgba(0, 0, 0, 0.45)",
              backdropFilter: "blur(4px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "16px",
            }}
            onClick={() => setLogoutModalOpen(false)}
          >
            <div
              style={{
                background: "#ffffff",
                borderRadius: "12px",
                padding: "24px",
                maxWidth: "380px",
                width: "100%",
                boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
                textAlign: "center",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div
                style={{
                  width: "48px",
                  height: "48px",
                  borderRadius: "50%",
                  background: "#fee2e2",
                  color: "#dc2626",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 16px",
                }}
              >
                <LogOut size={22} />
              </div>

              <h3 style={{ fontSize: "17px", fontWeight: "600", color: "#111827", marginBottom: "8px" }}>
                Confirm Sign Out
              </h3>
              <p style={{ fontSize: "13.5px", color: "#6b7280", marginBottom: "24px", lineHeight: "1.4" }}>
                Are you sure you want to sign out of Sakshi Finance? You will need to sign in again to access your account.
              </p>

              <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
                <button
                  type="button"
                  onClick={() => setLogoutModalOpen(false)}
                  style={{
                    flex: 1,
                    padding: "9px 16px",
                    borderRadius: "6px",
                    border: "1px solid #d1d5db",
                    background: "#ffffff",
                    color: "#374151",
                    fontSize: "13.5px",
                    fontWeight: "500",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleLogoutConfirm}
                  style={{
                    flex: 1,
                    padding: "9px 16px",
                    borderRadius: "6px",
                    border: "none",
                    background: "#dc2626",
                    color: "#ffffff",
                    fontSize: "13.5px",
                    fontWeight: "500",
                    cursor: "pointer",
                  }}
                >
                  Sign Out
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        @media (max-width: 900px) {
          .app-sidebar {
            transform: translateX(-100%);
          }
          .app-sidebar.open {
            transform: translateX(0) !important;
          }
          .app-main-content {
            margin-left: 0 !important;
          }
          .mobile-hamburger-btn {
            display: block !important;
          }
          .mobile-close-btn {
            display: block !important;
          }
        }
        .nav-item-link:hover {
          background: rgba(0, 113, 227, 0.05);
          color: var(--text-primary);
        }
      `}</style>
    </div>
  );
}
