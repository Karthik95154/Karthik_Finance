"use client";

import React from "react";
import AppShell from "@/components/AppShell";
import { Inbox, Mail, ShieldCheck } from "lucide-react";

export default function InboxPage() {
  return (
    <AppShell
      title="Inbox"
      subtitle="Email Ingestion Pipeline"
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
          <Inbox size={28} />
        </div>

        <h2
          style={{
            fontSize: "20px",
            fontWeight: "700",
            color: "var(--text-primary)",
            marginBottom: "8px",
          }}
        >
          Inbox
        </h2>

        <p
          style={{
            fontSize: "14px",
            color: "var(--text-secondary)",
            lineHeight: "1.6",
            marginBottom: "24px",
          }}
        >
          Email invoice ingestion will appear here.
        </p>

        <div
          style={{
            background: "var(--bg-main)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            padding: "12px 16px",
            fontSize: "12px",
            color: "var(--text-secondary)",
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <Mail size={15} color="var(--accent)" />
          <span>IMAP / Email webhook integration is currently configured separately.</span>
        </div>
      </div>
    </AppShell>
  );
}
