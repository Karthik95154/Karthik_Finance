"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { AlertOctagon, RefreshCw, LayoutDashboard, Home } from "lucide-react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("User Page Error:", error);
  }, [error]);

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
            backgroundColor: "#fff1f2",
            color: "#e11d48",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 24px",
            boxShadow: "0 4px 12px rgba(225, 29, 72, 0.15)",
          }}
        >
          <AlertOctagon size={36} />
        </div>

        {/* Status */}
        <div
          style={{
            fontSize: "13px",
            fontWeight: "700",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "#e11d48",
            marginBottom: "8px",
          }}
        >
          Application Notice
        </div>

        {/* Title */}
        <h1
          style={{
            fontSize: "24px",
            fontWeight: "800",
            color: "#0f172a",
            margin: "0 0 12px",
            letterSpacing: "-0.02em",
          }}
        >
          Something Went Wrong
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
          We encountered an unexpected issue while loading this page. Your data is safe and your accounting records are secure.
        </p>

        {/* Action Buttons */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          <button
            type="button"
            onClick={() => reset()}
            style={{
              backgroundColor: "#0071e3",
              color: "#ffffff",
              border: "none",
              padding: "11px 20px",
              borderRadius: "8px",
              fontSize: "14px",
              fontWeight: "600",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              transition: "background 0.15s ease",
            }}
          >
            <RefreshCw size={16} />
            <span>Try Again</span>
          </button>

          <Link
            href="/dashboard"
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
            <LayoutDashboard size={15} />
            <span>Back to Dashboard</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
