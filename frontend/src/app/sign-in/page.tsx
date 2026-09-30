"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import PublicNavbar from "@/components/PublicNavbar";
import PublicFooter from "@/components/PublicFooter";
import { API_BASE, invalidateZohoCache, clearAuthToken, changePassword } from "@/lib/api";
import { ShieldCheck, ArrowRight, Lock, Mail, AlertCircle, CheckCircle2, Loader2, KeyRound } from "lucide-react";

import { loginUser } from "@/lib/api";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forgotNotice, setForgotNotice] = useState<string | null>(null);

  // Forced Password Change Modal States
  const [showPasswordChangeModal, setShowPasswordChangeModal] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [changePasswordError, setChangePasswordError] = useState<string | null>(null);

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
      // Request JWT token from backend login auth endpoint
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password: password,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || "Sign in failed. Please check your credentials.");
        setIsLoading(false);
        return;
      }

      const data = await res.json();
      if (typeof window !== "undefined" && data.access_token) {
        clearAuthToken();
        invalidateZohoCache();
        sessionStorage.removeItem("sakshi_imap_settings_cache");
        sessionStorage.removeItem("sakshi_invoices_cache");
        sessionStorage.removeItem("sakshi_staged_docs_cache");

        localStorage.setItem("dev_auth_token", data.access_token);
        if (data.user) {
          localStorage.setItem("user_info", JSON.stringify(data.user));
        }

        // Check if user must change password on first login
        if (data.user?.must_change_password) {
          setIsLoading(false);
          setShowPasswordChangeModal(true);
          return;
        }
      }
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Invalid email or password.");
    } finally {
      setIsLoading(false);
    }
  };

  const validatePasswordRules = (pwd: string): string | null => {
    if (!pwd) return "Password cannot be empty.";
    if (pwd.includes(" ")) return "Password cannot contain spaces.";
    if (pwd.length < 8) return "Password must be at least 8 characters long.";
    if (!/[A-Z]/.test(pwd)) return "Password must contain at least 1 uppercase letter (A-Z).";
    if (!/[a-z]/.test(pwd)) return "Password must contain at least 1 lowercase letter (a-z).";
    if (!/[0-9]/.test(pwd)) return "Password must contain at least 1 number (0-9).";
    if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwd)) return "Password must contain at least 1 special character (!@#$%^&*...).";
    return null;
  };

  const handleChangePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setChangePasswordError(null);

    const ruleError = validatePasswordRules(newPassword);
    if (ruleError) {
      setChangePasswordError(ruleError);
      return;
    }

    if (newPassword !== confirmPassword) {
      setChangePasswordError("Confirm Password does not match Password.");
      return;
    }

    try {
      setIsChangingPassword(true);
      const res = await changePassword(newPassword);
      if (typeof window !== "undefined" && res.access_token) {
        localStorage.setItem("dev_auth_token", res.access_token);
        if (res.user) {
          localStorage.setItem("user_info", JSON.stringify(res.user));
        }
      }
      setShowPasswordChangeModal(false);
      router.push("/dashboard");
    } catch (err: any) {
      setChangePasswordError(err.message || "Failed to update password.");
    } finally {
      setIsChangingPassword(false);
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

      {/* Forced Password Change Modal */}
      {showPasswordChangeModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            background: "rgba(15, 23, 42, 0.6)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "#ffffff",
              borderRadius: "16px",
              maxWidth: "420px",
              width: "100%",
              padding: "28px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <div style={{ textAlign: "center", marginBottom: "20px" }}>
              <div
                style={{
                  width: "48px",
                  height: "48px",
                  borderRadius: "12px",
                  background: "var(--accent-subtle)",
                  color: "var(--accent)",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "12px",
                }}
              >
                <KeyRound size={24} />
              </div>
              <h2 style={{ fontSize: "18px", fontWeight: "700", color: "var(--text-primary)", margin: "0 0 6px 0" }}>
                Set Permanent Password
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: 0 }}>
                This is your first login with a temporary password. Please choose a new permanent password to secure your account.
              </p>
            </div>

            {changePasswordError && (
              <div
                style={{
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  borderRadius: "8px",
                  padding: "10px 14px",
                  marginBottom: "16px",
                  fontSize: "12.5px",
                  color: "#991b1b",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <AlertCircle size={15} />
                <span>{changePasswordError}</span>
              </div>
            )}

            <form onSubmit={handleChangePasswordSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12.5px", fontWeight: "600", color: "var(--text-primary)", marginBottom: "6px" }}>
                  New Password
                </label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="••••••••"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  disabled={isChangingPassword}
                  style={{
                    width: "100%",
                    height: "42px",
                    padding: "0 12px",
                    borderRadius: "8px",
                    border: "1px solid #d1d5db",
                    fontSize: "13.5px",
                  }}
                  required
                />
                
                {/* Visual Password Rule Checklist */}
                <div style={{ marginTop: "10px", padding: "10px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11.5px" }}>
                  <div style={{ fontWeight: "600", color: "#475569", marginBottom: "6px" }}>Password Rules:</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 8px" }}>
                    <div style={{ color: newPassword.length >= 8 ? "#166534" : "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                      <span>{newPassword.length >= 8 ? "✓" : "•"}</span> Minimum 8 characters
                    </div>
                    <div style={{ color: /[A-Z]/.test(newPassword) ? "#166534" : "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                      <span>{/[A-Z]/.test(newPassword) ? "✓" : "•"}</span> 1 Uppercase (A-Z)
                    </div>
                    <div style={{ color: /[a-z]/.test(newPassword) ? "#166534" : "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                      <span>{/[a-z]/.test(newPassword) ? "✓" : "•"}</span> 1 Lowercase (a-z)
                    </div>
                    <div style={{ color: /[0-9]/.test(newPassword) ? "#166534" : "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                      <span>{/[0-9]/.test(newPassword) ? "✓" : "•"}</span> 1 Number (0-9)
                    </div>
                    <div style={{ color: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(newPassword) ? "#166534" : "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                      <span>{/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(newPassword) ? "✓" : "•"}</span> 1 Special (!@#$...)
                    </div>
                    <div style={{ color: newPassword && !newPassword.includes(" ") ? "#166534" : "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                      <span>{newPassword && !newPassword.includes(" ") ? "✓" : "•"}</span> No spaces
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12.5px", fontWeight: "600", color: "var(--text-primary)", marginBottom: "6px" }}>
                  Confirm New Password
                </label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={isChangingPassword}
                  style={{
                    width: "100%",
                    height: "42px",
                    padding: "0 12px",
                    borderRadius: "8px",
                    border: "1px solid #d1d5db",
                    fontSize: "13.5px",
                  }}
                  required
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={isChangingPassword}
                style={{
                  width: "100%",
                  height: "42px",
                  fontSize: "13.5px",
                  fontWeight: "600",
                  marginTop: "6px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  borderRadius: "8px",
                }}
              >
                {isChangingPassword ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    <span>Saving New Password...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={16} />
                    <span>Save & Continue to Dashboard</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      <PublicFooter />
    </div>
  );
}
