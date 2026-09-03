"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import PublicNavbar from "@/components/PublicNavbar";
import PublicFooter from "@/components/PublicFooter";
import { ShieldCheck, ArrowRight, Lock, Mail, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forgotNotice, setForgotNotice] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setForgotNotice(null);

    // Client-side validation
    if (!email.trim()) {
      setError("Please enter your work email address.");
      return;
    }
    if (!email.includes("@") || !email.includes(".")) {
      setError("Please enter a valid email address.");
      return;
    }
    if (!password) {
      setError("Please enter your password.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    try {
      setIsLoading(true);
      // Request JWT token from backend auth endpoint
      const res = await fetch("http://127.0.0.1:8000/api/v1/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          dev_role: "ADMIN",
          dev_tenant_id: "default-tenant-001",
          dev_name: email.split("@")[0],
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (typeof window !== "undefined" && data.access_token) {
          localStorage.setItem("dev_auth_token", data.access_token);
        }
      }
      
      // Navigate to dashboard
      window.location.href = "/";
    } catch (err: any) {
      // Fallback navigation if network issue
      window.location.href = "/";
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = (e: React.MouseEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim()) {
      setError("Please enter your email above before requesting a password reset.");
    } else {
      setForgotNotice(`Password reset link will be sent to ${email} once mail services are active.`);
    }
  };

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
            maxWidth: "420px",
            background: "#ffffff",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "36px 32px",
            boxShadow: "var(--shadow-md)",
          }}
        >
          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: "28px" }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "10px",
                background: "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                margin: "0 auto 16px",
                boxShadow: "0 4px 12px rgba(0, 113, 227, 0.25)",
              }}
            >
              <ShieldCheck size={24} />
            </div>
            <h1
              style={{
                fontSize: "22px",
                fontWeight: "700",
                letterSpacing: "-0.02em",
                color: "var(--text-primary)",
                marginBottom: "6px",
              }}
            >
              Sign in to Finance
            </h1>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              Access your autonomous AP workspace and invoice ledger.
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div
              style={{
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: "var(--radius-sm)",
                padding: "10px 14px",
                marginBottom: "20px",
                fontSize: "13px",
                color: "#991b1b",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Forgot Notice */}
          {forgotNotice && (
            <div
              style={{
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                borderRadius: "var(--radius-sm)",
                padding: "10px 14px",
                marginBottom: "20px",
                fontSize: "13px",
                color: "#166534",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <CheckCircle2 size={16} />
              <span>{forgotNotice}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
            <div>
              <label
                htmlFor="email"
                style={{
                  display: "block",
                  fontSize: "13px",
                  fontWeight: "600",
                  color: "var(--text-primary)",
                  marginBottom: "6px",
                }}
              >
                Work Email
              </label>
              <div style={{ position: "relative" }}>
                <input
                  id="email"
                  type="email"
                  className="form-input"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                  style={{
                    paddingLeft: "36px",
                    width: "100%",
                  }}
                  autoComplete="email"
                />
                <Mail
                  size={16}
                  style={{
                    position: "absolute",
                    left: "12px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "var(--text-secondary)",
                  }}
                />
              </div>
            </div>

            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "6px",
                }}
              >
                <label
                  htmlFor="password"
                  style={{
                    fontSize: "13px",
                    fontWeight: "600",
                    color: "var(--text-primary)",
                  }}
                >
                  Password
                </label>
                <a
                  href="#forgot"
                  onClick={handleForgotPassword}
                  style={{
                    fontSize: "12px",
                    color: "var(--accent)",
                    fontWeight: "500",
                  }}
                >
                  Forgot password?
                </a>
              </div>
              <div style={{ position: "relative" }}>
                <input
                  id="password"
                  type="password"
                  className="form-input"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  style={{
                    paddingLeft: "36px",
                    width: "100%",
                  }}
                  autoComplete="current-password"
                />
                <Lock
                  size={16}
                  style={{
                    position: "absolute",
                    left: "12px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "var(--text-secondary)",
                  }}
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading}
              style={{
                width: "100%",
                padding: "11px",
                fontSize: "14px",
                fontWeight: "600",
                marginTop: "6px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                borderRadius: "var(--radius-sm)",
              }}
            >
              {isLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Signing In...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          {/* Footer Link */}
          <div
            style={{
              marginTop: "24px",
              paddingTop: "20px",
              borderTop: "1px solid var(--border-subtle)",
              textAlign: "center",
              fontSize: "13px",
              color: "var(--text-secondary)",
            }}
          >
            Don&apos;t have an account?{" "}
            <Link
              href="/sign-up"
              style={{
                color: "var(--accent)",
                fontWeight: "600",
              }}
            >
              Create Account
            </Link>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
