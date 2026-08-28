"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Inbox,
  FileSpreadsheet,
  Layers,
  UploadCloud,
  ShieldCheck,
  Menu,
  X,
  LogOut,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
} from "lucide-react";
import { getHealth, HealthResponse } from "@/lib/api";

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export default function AppShell({
  children,
  title,
  subtitle,
  actions,
}: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
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
          {/* Health Pill */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "11px",
              color: "var(--text-secondary)",
              marginBottom: "12px",
              padding: "6px 10px",
              background: "#ffffff",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: health?.status === "healthy" ? "#16a34a" : "#ca8a04",
                }}
              />
              <span style={{ fontWeight: "500" }}>
                {health?.status === "healthy" ? "Engine Active" : "Connecting..."}
              </span>
            </div>
            <span style={{ fontSize: "10px", color: "var(--text-tertiary)" }}>
              FastAPI
            </span>
          </div>

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
              <div
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "50%",
                  background: "var(--border-subtle)",
                  color: "var(--text-primary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "11px",
                  fontWeight: "700",
                }}
              >
                FA
              </div>
              <div style={{ fontSize: "12px", lineHeight: "1.2" }}>
                <div style={{ fontWeight: "600", color: "var(--text-primary)" }}>
                  Finance Admin
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-tertiary)" }}>
                  Review Specialist
                </div>
              </div>
            </div>

            <Link
              href="/"
              title="Sign Out to Landing"
              style={{
                color: "var(--text-secondary)",
                padding: "6px",
                borderRadius: "4px",
                display: "flex",
                alignItems: "center",
              }}
            >
              <LogOut size={15} />
            </Link>
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
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
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
