"use client";

import React from "react";
import Link from "next/link";
import { FileQuestion, ArrowLeft, LayoutDashboard, FileSpreadsheet, UploadCloud } from "lucide-react";

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "radial-gradient(ellipse at top, #f8fafc 0%, #f1f5f9 100%)",
        padding: "24px",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      <div
        style={{
          maxWidth: "520px",
          width: "100%",
          backgroundColor: "#ffffff",
          borderRadius: "16px",
          padding: "48px 36px",
          textAlign: "center",
          boxShadow: "0 20px 40px -15px rgba(0, 0, 0, 0.08), 0 0 1px 1px rgba(0, 0, 0, 0.05)",
          border: "1px solid #e2e8f0",
        }}
      >
        {/* Visual Badge */}
        <div
          style={{
            width: "72px",
            height: "72px",
            borderRadius: "50%",
            backgroundColor: "#fef2f2",
            color: "#ef4444",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 24px",
            boxShadow: "0 4px 12px rgba(239, 68, 68, 0.15)",
          }}
        >
          <FileQuestion size={36} />
        </div>

        {/* Status Code */}
        <div
          style={{
            fontSize: "14px",
            fontWeight: "700",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "#ef4444",
            marginBottom: "8px",
          }}
        >
          Error 404
        </div>

        {/* Title */}
        <h1
          style={{
            fontSize: "26px",
            fontWeight: "800",
            color: "#0f172a",
            margin: "0 0 12px",
            letterSpacing: "-0.02em",
          }}
        >
          Page Not Found
        </h1>

        {/* Friendly User Explanation */}
        <p
          style={{
            fontSize: "14px",
            color: "#64748b",
            lineHeight: "1.6",
            margin: "0 0 32px",
          }}
        >
          We couldn't find the invoice, report, or page you were looking for. It may have been moved, deleted, or the URL might be incorrect.
        </p>

        {/* Action Buttons */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          <Link
            href="/dashboard"
            style={{
              backgroundColor: "#0071e3",
              color: "#ffffff",
              padding: "11px 20px",
              borderRadius: "8px",
              fontSize: "14px",
              fontWeight: "600",
              textDecoration: "none",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              transition: "background 0.15s ease",
            }}
          >
            <LayoutDashboard size={16} />
            <span>Return to Dashboard</span>
          </Link>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <Link
              href="/finance/invoices"
              style={{
                backgroundColor: "#f8fafc",
                color: "#334155",
                border: "1px solid #cbd5e1",
                padding: "10px 16px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
                textDecoration: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
              }}
            >
              <FileSpreadsheet size={15} />
              <span>All Invoices</span>
            </Link>

            <Link
              href="/finance/upload"
              style={{
                backgroundColor: "#f8fafc",
                color: "#334155",
                border: "1px solid #cbd5e1",
                padding: "10px 16px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
                textDecoration: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
              }}
            >
              <UploadCloud size={15} />
              <span>Upload Invoice</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
