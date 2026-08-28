"use client";

import React from "react";
import AppShell from "@/components/AppShell";
import { Layers, Puzzle, ShieldCheck } from "lucide-react";

export default function IntegrationsPage() {
  return (
    <AppShell
      title="Integrations"
      subtitle="External Accounting & ERP Connections"
    >
      <div
        style={{
          maxWidth: "600px",
          margin: "40px auto",
          textAlign: "center",
          background: "#ffffff",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          padding: "48px 32px",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            background: "rgba(0, 113, 227, 0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--accent)",
            margin: "0 auto 16px",
          }}
        >
          <Layers size={28} />
        </div>

        <h2
          style={{
            fontSize: "20px",
            fontWeight: "700",
            color: "var(--text-primary)",
            marginBottom: "8px",
          }}
        >
          Integrations
        </h2>

        <p
          style={{
            fontSize: "14px",
            color: "var(--text-secondary)",
            lineHeight: "1.6",
            marginBottom: "24px",
          }}
        >
          Connect and synchronize your finance ERP and accounting platforms.
        </p>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            textAlign: "left",
            marginBottom: "20px",
          }}
        >
          <a
            href="/finance/settings"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px",
              background: "#ffffff",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-sm)",
              textDecoration: "none",
              transition: "border-color var(--transition-fast)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div
                style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "8px",
                  background: "rgba(0, 113, 227, 0.08)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--accent)",
                }}
              >
                <ShieldCheck size={22} />
              </div>
              <div>
                <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-primary)" }}>
                  Zoho Books
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  OAuth 2.0, Chart of Accounts, Tax Rates, and Bill Export
                </div>
              </div>
            </div>
            <span
              className="btn btn-secondary"
              style={{ padding: "6px 12px", fontSize: "12px" }}
            >
              Configure →
            </span>
          </a>
        </div>
      </div>
    </AppShell>
  );
}
