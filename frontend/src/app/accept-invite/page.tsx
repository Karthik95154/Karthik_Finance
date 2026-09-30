"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import PublicNavbar from "@/components/PublicNavbar";
import PublicFooter from "@/components/PublicFooter";
import {
  validateInvitationToken,
  sendInviteOtp,
  verifyInviteOtp,
  acceptInvitation,
  clearAuthToken,
  invalidateZohoCache,
} from "@/lib/api";
import {
  ShieldCheck,
  Mail,
  Lock,
  User,
  AlertCircle,
  Loader2,
  ArrowLeft,
  CheckCircle2,
  KeyRound,
  RefreshCw,
} from "lucide-react";

function AcceptInviteContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [invitationState, setInvitationState] = useState<{
    isLoading: boolean;
    error: string | null;
    email: string | null;
    maskedEmail: string | null;
    role: string | null;
  }>({
    isLoading: true,
    error: null,
    email: null,
    maskedEmail: null,
    role: null,
  });

  // OTP Stage States
  const [otp, setOtp] = useState("");
  const [otpVerified, setOtpVerified] = useState(false);
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);
  const [isSendingOtp, setIsSendingOtp] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [otpSuccessMsg, setOtpSuccessMsg] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  // Account Setup States
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Countdown timer effect for OTP resend cooldown
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  useEffect(() => {
    if (!token) {
      setInvitationState({
        isLoading: false,
        error: "Invitation token is missing from the link.",
        email: null,
        maskedEmail: null,
        role: null,
      });
      return;
    }

    validateInvitationToken(token)
      .then((data) => {
        setInvitationState({
          isLoading: false,
          error: null,
          email: data.email,
          maskedEmail: data.masked_email || data.email,
          role: data.role,
        });
        if (data.otp_verified) {
          setOtpVerified(true);
        }
        setFullName(data.email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()));
      })
      .catch((err: any) => {
        setInvitationState({
          isLoading: false,
          error: err.message || "Invalid or expired invitation token.",
          email: null,
          maskedEmail: null,
          role: null,
        });
      });
  }, [token]);

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setOtpError(null);
    setOtpSuccessMsg(null);

    const cleanOtp = otp.trim();
    if (!cleanOtp) {
      setOtpError("Please enter the 6-digit verification code.");
      return;
    }
    if (cleanOtp.length < 6) {
      setOtpError("Verification code must be 6 digits.");
      return;
    }

    try {
      setIsVerifyingOtp(true);
      const res = await verifyInviteOtp(token, cleanOtp);
      if (res.success) {
        setOtpVerified(true);
        setOtpSuccessMsg("Email address verified successfully. You may now create your password.");
      }
    } catch (err: any) {
      setOtpError(err.message || "Verification failed. Please check the code and try again.");
    } finally {
      setIsVerifyingOtp(false);
    }
  };

  const handleResendOtp = async () => {
    if (resendCooldown > 0 || isSendingOtp) return;
    setOtpError(null);
    setOtpSuccessMsg(null);

    try {
      setIsSendingOtp(true);
      const res = await sendInviteOtp(token);
      setOtpSuccessMsg(res.message || "A new verification code has been sent.");
      setResendCooldown(30);
    } catch (err: any) {
      setOtpError(err.message || "Failed to resend verification code.");
    } finally {
      setIsSendingOtp(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!otpVerified) {
      setSubmitError("Please verify your email address using the verification code first.");
      return;
    }

    if (!password) {
      setSubmitError("Please enter a password.");
      return;
    }
    if (password.length < 6) {
      setSubmitError("Password must be at least 6 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setSubmitError("Passwords do not match. Please re-enter.");
      return;
    }

    try {
      setIsSubmitting(true);
      const data = await acceptInvitation({
        token,
        password,
        full_name: fullName.trim() || undefined,
      });

      if (typeof window !== "undefined" && data.access_token) {
        clearAuthToken();
        invalidateZohoCache();
        sessionStorage.clear();
        localStorage.setItem("dev_auth_token", data.access_token);
        if (data.user) {
          localStorage.setItem("user_info", JSON.stringify(data.user));
        }
      }
      router.push("/dashboard");
    } catch (err: any) {
      setSubmitError(err.message || "Failed to create account. Please try again.");
      setIsSubmitting(false);
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
          {/* Loading State */}
          {invitationState.isLoading && (
            <div style={{ textAlign: "center", padding: "40px 0" }}>
              <Loader2 size={36} className="animate-spin" style={{ color: "var(--accent)", margin: "0 auto 16px" }} />
              <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>Verifying invitation link...</p>
            </div>
          )}

          {/* Invalid / Expired State */}
          {!invitationState.isLoading && invitationState.error && (
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  width: "54px",
                  height: "54px",
                  borderRadius: "16px",
                  background: "#fff1f0",
                  border: "1px solid #ffa39e",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#e60000",
                  margin: "0 auto 16px",
                }}
              >
                <AlertCircle size={28} />
              </div>
              <h1
                style={{
                  fontSize: "20px",
                  fontWeight: "700",
                  color: "var(--text-primary)",
                  marginBottom: "8px",
                }}
              >
                Invitation Error
              </h1>
              <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "24px", lineHeight: "1.5" }}>
                {invitationState.error}
              </p>
              <Link
                href="/sign-in"
                className="btn btn-primary"
                style={{
                  width: "100%",
                  padding: "11px 20px",
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
          )}

          {/* Valid Invitation Flow */}
          {!invitationState.isLoading && !invitationState.error && (
            <div>
              <div style={{ textAlign: "center", marginBottom: "24px" }}>
                <div
                  style={{
                    width: "50px",
                    height: "50px",
                    borderRadius: "14px",
                    background: otpVerified
                      ? "linear-gradient(135deg, #10b981 0%, #059669 100%)"
                      : "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#ffffff",
                    margin: "0 auto 14px",
                    boxShadow: otpVerified ? "0 6px 16px rgba(16, 185, 129, 0.3)" : "0 6px 16px rgba(0, 113, 227, 0.3)",
                  }}
                >
                  {otpVerified ? <CheckCircle2 size={26} /> : <ShieldCheck size={26} />}
                </div>
                <h1
                  style={{
                    fontSize: "22px",
                    fontWeight: "700",
                    color: "var(--text-primary)",
                    marginBottom: "6px",
                  }}
                >
                  {otpVerified ? "Create your Password" : "Verify your Email"}
                </h1>
                <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.4" }}>
                  {otpVerified ? (
                    <span>Email verified. Set up your password to activate your account.</span>
                  ) : (
                    <span>
                      A 6-digit verification code was sent to{" "}
                      <strong style={{ color: "var(--text-primary)" }}>{invitationState.maskedEmail}</strong>.
                    </span>
                  )}
                </p>
              </div>

              {/* Status & Error Banners */}
              {otpSuccessMsg && (
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "var(--radius-sm)",
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    color: "#166534",
                    fontSize: "13px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "20px",
                  }}
                >
                  <CheckCircle2 size={16} />
                  <span>{otpSuccessMsg}</span>
                </div>
              )}

              {otpError && (
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "var(--radius-sm)",
                    background: "#fff1f0",
                    border: "1px solid #ffa39e",
                    color: "#e60000",
                    fontSize: "13px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "20px",
                  }}
                >
                  <AlertCircle size={16} />
                  <span>{otpError}</span>
                </div>
              )}

              {submitError && (
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "var(--radius-sm)",
                    background: "#fff1f0",
                    border: "1px solid #ffa39e",
                    color: "#e60000",
                    fontSize: "13px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "20px",
                  }}
                >
                  <AlertCircle size={16} />
                  <span>{submitError}</span>
                </div>
              )}

              {/* STAGE 1: OTP VERIFICATION FIELD */}
              {!otpVerified && (
                <form onSubmit={handleVerifyOtp} style={{ marginBottom: "24px" }}>
                  <div style={{ marginBottom: "16px" }}>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: "600",
                        color: "var(--text-secondary)",
                        marginBottom: "6px",
                      }}
                    >
                      Email Verification Code (OTP)
                    </label>
                    <div style={{ position: "relative" }}>
                      <KeyRound
                        size={17}
                        style={{
                          position: "absolute",
                          left: "12px",
                          top: "50%",
                          transform: "translateY(-50%)",
                          color: "var(--text-tertiary)",
                        }}
                      />
                      <input
                        type="text"
                        maxLength={6}
                        value={otp}
                        onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                        placeholder="Enter 6-digit code"
                        required
                        autoFocus
                        style={{
                          width: "100%",
                          padding: "11px 12px 11px 38px",
                          borderRadius: "var(--radius-sm)",
                          border: "1.5px solid var(--accent)",
                          background: "#ffffff",
                          fontSize: "16px",
                          letterSpacing: "4px",
                          fontWeight: "700",
                          fontFamily: "monospace",
                        }}
                      />
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "10px" }}>
                    <button
                      type="submit"
                      disabled={isVerifyingOtp || otp.length < 6}
                      className="btn btn-primary"
                      style={{
                        flex: 1,
                        padding: "11px 16px",
                        fontSize: "14px",
                        fontWeight: "600",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "8px",
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      {isVerifyingOtp ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          <span>Verifying Code...</span>
                        </>
                      ) : (
                        <>
                          <ShieldCheck size={16} />
                          <span>Verify Email OTP</span>
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={handleResendOtp}
                      disabled={resendCooldown > 0 || isSendingOtp}
                      className="btn"
                      style={{
                        padding: "11px 14px",
                        fontSize: "13px",
                        fontWeight: "600",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        background: "#f8f9fa",
                        color: resendCooldown > 0 ? "#86868b" : "var(--text-primary)",
                        cursor: resendCooldown > 0 || isSendingOtp ? "not-allowed" : "pointer",
                      }}
                    >
                      <RefreshCw size={14} className={isSendingOtp ? "animate-spin" : ""} />
                      <span>{resendCooldown > 0 ? `Resend in ${resendCooldown}s` : "Resend Code"}</span>
                    </button>
                  </div>
                </form>
              )}

              {/* STAGE 2: PASSWORD CREATION FORM (UNLOCKED ONLY AFTER OTP VERIFICATION) */}
              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
                {/* Invited Email (Read-Only) */}
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: "600",
                      color: "var(--text-secondary)",
                      marginBottom: "6px",
                    }}
                  >
                    Invited Email Address
                  </label>
                  <div style={{ position: "relative" }}>
                    <Mail
                      size={17}
                      style={{
                        position: "absolute",
                        left: "12px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        color: "var(--text-tertiary)",
                      }}
                    />
                    <input
                      type="email"
                      value={invitationState.email || ""}
                      readOnly
                      disabled
                      style={{
                        width: "100%",
                        padding: "10px 12px 10px 38px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        background: "#f5f5f7",
                        color: "var(--text-secondary)",
                        fontSize: "13.5px",
                        cursor: "not-allowed",
                      }}
                    />
                  </div>
                </div>

                {/* Full Name */}
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: "600",
                      color: "var(--text-secondary)",
                      marginBottom: "6px",
                    }}
                  >
                    Full Name
                  </label>
                  <div style={{ position: "relative" }}>
                    <User
                      size={17}
                      style={{
                        position: "absolute",
                        left: "12px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        color: "var(--text-tertiary)",
                      }}
                    />
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="e.g. Sai Vignesh"
                      required
                      disabled={!otpVerified}
                      style={{
                        width: "100%",
                        padding: "10px 12px 10px 38px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        background: otpVerified ? "#ffffff" : "#f5f5f7",
                        fontSize: "13.5px",
                        cursor: otpVerified ? "text" : "not-allowed",
                      }}
                    />
                  </div>
                </div>

                {/* Password */}
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: "600",
                      color: "var(--text-secondary)",
                      marginBottom: "6px",
                    }}
                  >
                    Create Password {!otpVerified && "(Verify OTP first to unlock)"}
                  </label>
                  <div style={{ position: "relative" }}>
                    <Lock
                      size={17}
                      style={{
                        position: "absolute",
                        left: "12px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        color: "var(--text-tertiary)",
                      }}
                    />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Minimum 6 characters"
                      required
                      disabled={!otpVerified}
                      style={{
                        width: "100%",
                        padding: "10px 12px 10px 38px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        background: otpVerified ? "#ffffff" : "#f5f5f7",
                        fontSize: "13.5px",
                        cursor: otpVerified ? "text" : "not-allowed",
                      }}
                    />
                  </div>
                </div>

                {/* Confirm Password */}
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: "600",
                      color: "var(--text-secondary)",
                      marginBottom: "6px",
                    }}
                  >
                    Confirm Password
                  </label>
                  <div style={{ position: "relative" }}>
                    <Lock
                      size={17}
                      style={{
                        position: "absolute",
                        left: "12px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        color: "var(--text-tertiary)",
                      }}
                    />
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter password"
                      required
                      disabled={!otpVerified}
                      style={{
                        width: "100%",
                        padding: "10px 12px 10px 38px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        background: otpVerified ? "#ffffff" : "#f5f5f7",
                        fontSize: "13.5px",
                        cursor: otpVerified ? "text" : "not-allowed",
                      }}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={!otpVerified || isSubmitting}
                  className="btn btn-primary"
                  style={{
                    width: "100%",
                    padding: "11px 20px",
                    fontSize: "14px",
                    fontWeight: "600",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "8px",
                    borderRadius: "var(--radius-sm)",
                    marginTop: "8px",
                    opacity: !otpVerified ? 0.6 : 1,
                    cursor: !otpVerified || isSubmitting ? "not-allowed" : "pointer",
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      <span>Creating Account...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={16} />
                      <span>Activate Account & Log In</span>
                    </>
                  )}
                </button>
              </form>
            </div>
          )}
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense
      fallback={
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--bg-main)" }}>
          <PublicNavbar />
          <main style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "var(--text-secondary)", fontSize: "14px" }}>
              <Loader2 size={20} className="animate-spin" />
              <span>Loading invitation details...</span>
            </div>
          </main>
          <PublicFooter />
        </div>
      }
    >
      <AcceptInviteContent />
    </Suspense>
  );
}
