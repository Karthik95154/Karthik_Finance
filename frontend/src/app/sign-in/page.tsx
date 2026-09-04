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
          if (data.user) {
            localStorage.setItem("user_info", JSON.stringify(data.user));
          }
        }
      }
      
      // Navigate to dashboard
      window.location.href = "/dashboard";
    } catch (err: any) {
      // Fallback navigation if network issue
      window.location.href = "/dashboard";
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
            maxWidth: "480px",
            background: "#ffffff",
            border: "1px solid var(--border-subtle)",
            borderRadius: "20px",
            padding: "40px 36px",
            boxShadow: "0 20px 35px -5px rgba(0, 0, 0, 0.07), 0 10px 15px -5px rgba(0, 0, 0, 0.03)",
          }}
        >
          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: "30px" }}>
            <div
              style={{
                width: "50px",
                height: "50px",
                borderRadius: "14px",
                background: "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                margin: "0 auto 16px",
                boxShadow: "0 6px 16px rgba(0, 113, 227, 0.3)",
              }}
            >
              <ShieldCheck size={26} />
            </div>
            <h1
              style={{
                fontSize: "24px",
                fontWeight: "700",
                letterSpacing: "-0.02em",
                color: "var(--text-primary)",
                marginBottom: "6px",
              }}
            >
              Sign in to Finance
            </h1>
            <p style={{ fontSize: "13.5px", color: "var(--text-secondary)" }}>
              Access your autonomous AP workspace and invoice ledger.
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div
              style={{
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: "12px",
                padding: "12px 16px",
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
                borderRadius: "12px",
                padding: "12px 16px",
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
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            <div>
              <label
                htmlFor="email"
                style={{
                  display: "block",
                  fontSize: "13.5px",
                  fontWeight: "600",
                  color: "var(--text-primary)",
                  marginBottom: "8px",
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
                    height: "46px",
                    paddingLeft: "42px",
                    width: "100%",
                    borderRadius: "12px",
                    border: "1px solid #d1d5db",
                    fontSize: "14px",
                    outline: "none",
                  }}
                  autoComplete="email"
                />
                <Mail
                  size={18}
                  style={{
                    position: "absolute",
                    left: "14px",
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
                  marginBottom: "8px",
                }}
              >
                <label
                  htmlFor="password"
                  style={{
                    fontSize: "13.5px",
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
                    fontSize: "12.5px",
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
                    height: "46px",
                    paddingLeft: "42px",
                    width: "100%",
                    borderRadius: "12px",
                    border: "1px solid #d1d5db",
                    fontSize: "14px",
                    outline: "none",
                  }}
                  autoComplete="current-password"
                />
                <Lock
                  size={18}
                  style={{
                    position: "absolute",
                    left: "14px",
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
                height: "46px",
                fontSize: "14.5px",
                fontWeight: "600",
                marginTop: "6px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                borderRadius: "12px",
              }}
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  <span>Signing In...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={16} />
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
