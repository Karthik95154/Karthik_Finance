"use client";

import React from "react";
import Link from "next/link";
import PublicNavbar from "@/components/PublicNavbar";
import PublicFooter from "@/components/PublicFooter";
import { ShieldAlert, ArrowLeft } from "lucide-react";

export default function SignUpPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "var(--bg-main)",
      }}
    >
      <PublicNavbar />

      <main
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "48px 24px",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "480px",
            background: "#ffffff",
            border: "1px solid var(--border-subtle)",
            borderRadius: "20px",
            padding: "40px 36px",
            boxShadow: "0 20px 35px -5px rgba(0, 0, 0, 0.07), 0 10px 15px -5px rgba(0, 0, 0, 0.03)",
            textAlign: "center",
          }}
        >
          {/* Header Icon */}
          <div
            style={{
              width: "60px",
              height: "60px",
              borderRadius: "16px",
              background: "#fff1f0",
              border: "1px solid #ffa39e",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#e60000",
              margin: "0 auto 20px",
            }}
          >
            <ShieldAlert size={30} />
          </div>

          <h1
            style={{
              fontSize: "22px",
              fontWeight: "700",
              letterSpacing: "-0.02em",
              color: "var(--text-primary)",
              marginBottom: "12px",
            }}
          >
            Access Restricted
          </h1>

          <p
            style={{
              fontSize: "14px",
              lineHeight: "1.6",
              color: "var(--text-secondary)",
              marginBottom: "28px",
            }}
          >
            Your account has not been invited to Sakshi Finance. Please contact your administrator for an invitation link.
          </p>

          <Link
            href="/sign-in"
            className="btn btn-primary"
            style={{
              width: "100%",
              padding: "12px 20px",
              fontSize: "14px",
              fontWeight: "600",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              borderRadius: "var(--radius-sm)",
              textDecoration: "none",
            }}
          >
            <ArrowLeft size={16} />
            <span>Return to Login</span>
          </Link>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
