"use client";

import React, { useState, useEffect } from "react";
import AppShell from "@/components/AppShell";
import {
  getUsers,
  getInvitations,
  createUser,
  inviteUser,
  resendInvitation,
  revokeInvitation,
  deactivateUser,
  reactivateUser,
  UserManagementItem,
  UserInvitationItem,
} from "@/lib/api";
import {
  Users,
  UserPlus,
  Mail,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  Search,
  AlertTriangle,
  Copy,
  Check,
  Loader2,
  X,
  UserCheck,
  UserX,
  Plus,
  Trash2,
  ChevronDown,
} from "lucide-react";

export default function AdminUsersPage() {
  const [activeTab, setActiveTab] = useState<"users" | "invitations">("users");
  const [users, setUsers] = useState<UserManagementItem[]>([]);
  const [invitations, setInvitations] = useState<UserInvitationItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Modal states
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [isSubmittingInvite, setIsSubmittingInvite] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccessMsg, setInviteSuccessMsg] = useState<string | null>(null);
  const [emailSentStatus, setEmailSentStatus] = useState<boolean>(true);
  const [createdInviteUrl, setCreatedInviteUrl] = useState<string | null>(null);
  const [copiedUrl, setCopiedUrl] = useState(false);

  // Role management
  const [availableRoles, setAvailableRoles] = useState<Array<{ value: string; label: string }>>([
    { value: "FINANCE_USER", label: "Finance User" },
    { value: "FINANCE_ADMIN", label: "Finance Admin" },
  ]);
  const [selectedInviteRole, setSelectedInviteRole] = useState("FINANCE_USER");
  const [showAddRoleInput, setShowAddRoleInput] = useState(false);
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleError, setNewRoleError] = useState<string | null>(null);

  // Action confirmation states
  const [deactivateModalUser, setDeactivateModalUser] = useState<UserManagementItem | null>(null);
  const [reactivateModalUser, setReactivateModalUser] = useState<UserManagementItem | null>(null);
  const [revokeModalInv, setRevokeModalInv] = useState<UserInvitationItem | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [uList, iList] = await Promise.all([getUsers(), getInvitations()]);
      setUsers(uList);
      setInvitations(iList);
    } catch (err: any) {
      setError(err.message || "Failed to load administration data. Please verify your permissions.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Direct Create User Modal states
  const [createdTempPassword, setCreatedTempPassword] = useState<string | null>(null);

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError(null);
    setInviteSuccessMsg(null);
    setCreatedInviteUrl(null);
    setCreatedTempPassword(null);

    if (!inviteEmail.trim() || !inviteEmail.includes("@")) {
      setInviteError("Please enter a valid email address.");
      return;
    }

    try {
      setIsSubmittingInvite(true);
      const res = await createUser({
        email: inviteEmail.trim().toLowerCase(),
        full_name: inviteName.trim() || undefined,
        role: selectedInviteRole,
      });

      setCreatedTempPassword(res.temporary_password);
      setInviteSuccessMsg(res.message);
      setInviteEmail("");
      setInviteName("");
      fetchData();
    } catch (err: any) {
      setInviteError(err.message || "Failed to create user account.");
    } finally {
      setIsSubmittingInvite(false);
    }
  };

  const handleCopyUrl = (url: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(url);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    }
  };

  const handleDeactivate = async () => {
    if (!deactivateModalUser) return;
    try {
      setActionLoading(true);
      setActionError(null);
      await deactivateUser(deactivateModalUser.id);
      setDeactivateModalUser(null);
      fetchData();
    } catch (err: any) {
      setActionError(err.message || "Failed to deactivate user.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReactivate = async () => {
    if (!reactivateModalUser) return;
    try {
      setActionLoading(true);
      setActionError(null);
      await reactivateUser(reactivateModalUser.id);
      setReactivateModalUser(null);
      fetchData();
    } catch (err: any) {
      setActionError(err.message || "Failed to reactivate user.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async () => {
    if (!revokeModalInv) return;
    try {
      setActionLoading(true);
      setActionError(null);
      await revokeInvitation(revokeModalInv.id);
      setRevokeModalInv(null);
      fetchData();
    } catch (err: any) {
      setActionError(err.message || "Failed to revoke invitation.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResend = async (invId: string) => {
    try {
      setActionLoading(true);
      setActionError(null);
      setInviteError(null);
      setInviteSuccessMsg(null);
      const res = await resendInvitation(invId);
      if (res.invitation_url) {
        setCreatedInviteUrl(res.invitation_url);
        setInviteSuccessMsg(res.message);
        setEmailSentStatus(res.email_sent ?? true);
        setInviteModalOpen(true);
      }
      fetchData();
    } catch (err: any) {
      setActionError(err.message || "Failed to resend invitation.");
    } finally {
      setActionLoading(false);
    }
  };

  // Filtered lists
  const filteredUsers = users.filter(
    (u) =>
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (u.full_name && u.full_name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const filteredInvitations = invitations.filter((i) =>
    i.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <AppShell
      title="Administration"
      subtitle="Manage users and access to Sakshi Finance."
      actions={
        <button
          onClick={() => {
            setCreatedInviteUrl(null);
            setInviteError(null);
            setInviteSuccessMsg(null);
            setInviteModalOpen(true);
          }}
          className="btn btn-primary"
          style={{
            padding: "9px 16px",
            fontSize: "13px",
            fontWeight: "600",
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            borderRadius: "var(--radius-sm)",
          }}
        >
          <UserPlus size={16} />
          <span>Create User</span>
        </button>
      }
    >
      <div style={{ maxWidth: "1200px", margin: "0 auto", paddingBottom: "40px" }}>
        {/* Error Banner */}
        {(error || actionError) && (
          <div
            style={{
              padding: "12px 16px",
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
            <AlertTriangle size={16} />
            <span>{error || actionError}</span>
          </div>
        )}

        {/* Header Tabs & Controls */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "16px",
            marginBottom: "24px",
            borderBottom: "1px solid var(--border-subtle)",
            paddingBottom: "16px",
          }}
        >
          {/* Navigation Tabs */}
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={() => setActiveTab("users")}
              style={{
                padding: "8px 16px",
                fontSize: "13.5px",
                fontWeight: activeTab === "users" ? "600" : "500",
                color: activeTab === "users" ? "var(--accent)" : "var(--text-secondary)",
                background: activeTab === "users" ? "rgba(0, 113, 227, 0.08)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <Users size={16} />
              <span>Active Users ({users.length})</span>
            </button>

            <button
              onClick={() => setActiveTab("invitations")}
              style={{
                padding: "8px 16px",
                fontSize: "13.5px",
                fontWeight: activeTab === "invitations" ? "600" : "500",
                color: activeTab === "invitations" ? "var(--accent)" : "var(--text-secondary)",
                background: activeTab === "invitations" ? "rgba(0, 113, 227, 0.08)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <Mail size={16} />
              <span>
                Pending Invitations ({invitations.filter((i) => i.status === "PENDING").length})
              </span>
            </button>
          </div>

          {/* Search Bar */}
          <div style={{ position: "relative", width: "260px" }}>
            <Search
              size={15}
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
              placeholder="Search by email or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px 8px 34px",
                fontSize: "13px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-subtle)",
                background: "#ffffff",
              }}
            />
          </div>
        </div>

        {/* Loading Spinner */}
        {isLoading && (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <Loader2 size={32} className="animate-spin" style={{ color: "var(--accent)", margin: "0 auto 12px" }} />
            <p style={{ fontSize: "13.5px", color: "var(--text-secondary)" }}>Loading administration details...</p>
          </div>
        )}

        {/* Users Table */}
        {!isLoading && activeTab === "users" && (
          <div>
            {filteredUsers.length === 0 ? (
              <div
                style={{
                  background: "#ffffff",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  padding: "48px 24px",
                  textAlign: "center",
                }}
              >
                <Users size={40} style={{ color: "var(--text-tertiary)", margin: "0 auto 12px" }} />
                <h3 style={{ fontSize: "16px", fontWeight: "600", marginBottom: "6px" }}>No users found</h3>
                <p style={{ fontSize: "13.5px", color: "var(--text-secondary)", marginBottom: "20px" }}>
                  Invite your first Finance team member to grant them access to Sakshi Finance.
                </p>
                <button
                  onClick={() => setInviteModalOpen(true)}
                  className="btn btn-primary"
                  style={{
                    padding: "9px 16px",
                    fontSize: "13px",
                    fontWeight: "600",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <UserPlus size={16} />
                  <span>Invite User</span>
                </button>
              </div>
            ) : (
              <div
                style={{
                  background: "#ffffff",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  overflow: "hidden",
                  boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)",
                }}
              >
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                  <thead>
                    <tr
                      style={{
                        background: "#fafafa",
                        borderBottom: "1px solid var(--border-subtle)",
                        textAlign: "left",
                      }}
                    >
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>User</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Role</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Account Status</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Joined Date</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)", textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((u) => (
                      <tr key={u.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "14px 16px" }}>
                          <div style={{ fontWeight: "600", color: "var(--text-primary)" }}>
                            {u.full_name || u.email.split("@")[0]}
                          </div>
                          <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{u.email}</div>
                        </td>
                        <td style={{ padding: "14px 16px" }}>
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: "700",
                              padding: "3px 8px",
                              borderRadius: "4px",
                              textTransform: "uppercase",
                              background: u.role === "ADMIN" ? "#e6f4ff" : "#f5f5f7",
                              color: u.role === "ADMIN" ? "#0071e3" : "var(--text-secondary)",
                              border: u.role === "ADMIN" ? "1px solid #91caff" : "1px solid var(--border-subtle)",
                            }}
                          >
                            {u.role}
                          </span>
                        </td>
                        <td style={{ padding: "14px 16px" }}>
                          {u.is_active ? (
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                                fontSize: "12px",
                                fontWeight: "600",
                                color: "#389e0d",
                                background: "#f6ffed",
                                border: "1px solid #b7eb8f",
                                padding: "2px 8px",
                                borderRadius: "4px",
                              }}
                            >
                              <CheckCircle2 size={14} /> Active
                            </span>
                          ) : (
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                                fontSize: "12px",
                                fontWeight: "600",
                                color: "#cf1322",
                                background: "#fff1f0",
                                border: "1px solid #ffa39e",
                                padding: "2px 8px",
                                borderRadius: "4px",
                              }}
                            >
                              <XCircle size={14} /> Inactive
                            </span>
                          )}
                        </td>
                        <td style={{ padding: "14px 16px", color: "var(--text-secondary)" }}>
                          {new Date(u.created_at).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </td>
                        <td style={{ padding: "14px 16px", textAlign: "right" }}>
                          {u.is_active ? (
                            <button
                              onClick={() => setDeactivateModalUser(u)}
                              style={{
                                border: "1px solid #ffa39e",
                                background: "#ffffff",
                                color: "#cf1322",
                                padding: "5px 12px",
                                borderRadius: "var(--radius-sm)",
                                fontSize: "12px",
                                fontWeight: "600",
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                              }}
                            >
                              <UserX size={14} /> Deactivate
                            </button>
                          ) : (
                            <button
                              onClick={() => setReactivateModalUser(u)}
                              style={{
                                border: "1px solid #b7eb8f",
                                background: "#ffffff",
                                color: "#389e0d",
                                padding: "5px 12px",
                                borderRadius: "var(--radius-sm)",
                                fontSize: "12px",
                                fontWeight: "600",
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                              }}
                            >
                              <UserCheck size={14} /> Reactivate
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Invitations Table */}
        {!isLoading && activeTab === "invitations" && (
          <div>
            {filteredInvitations.length === 0 ? (
              <div
                style={{
                  background: "#ffffff",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  padding: "48px 24px",
                  textAlign: "center",
                }}
              >
                <Mail size={40} style={{ color: "var(--text-tertiary)", margin: "0 auto 12px" }} />
                <h3 style={{ fontSize: "16px", fontWeight: "600", marginBottom: "6px" }}>No pending invitations</h3>
                <p style={{ fontSize: "13.5px", color: "var(--text-secondary)" }}>
                  All invited team members have accepted or no invitations have been sent yet.
                </p>
              </div>
            ) : (
              <div
                style={{
                  background: "#ffffff",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  overflow: "hidden",
                  boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)",
                }}
              >
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                  <thead>
                    <tr
                      style={{
                        background: "#fafafa",
                        borderBottom: "1px solid var(--border-subtle)",
                        textAlign: "left",
                      }}
                    >
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Invited Email</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Role</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Status</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Sent Date</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" }}>Expires</th>
                      <th style={{ padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)", textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredInvitations.map((i) => (
                      <tr key={i.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "14px 16px", fontWeight: "600", color: "var(--text-primary)" }}>{i.email}</td>
                        <td style={{ padding: "14px 16px" }}>
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: "700",
                              padding: "3px 8px",
                              borderRadius: "4px",
                              background: "#f5f5f7",
                              color: "var(--text-secondary)",
                              border: "1px solid var(--border-subtle)",
                            }}
                          >
                            FINANCE_USER
                          </span>
                        </td>
                        <td style={{ padding: "14px 16px" }}>
                          <span
                            style={{
                              fontSize: "11.5px",
                              fontWeight: "600",
                              padding: "4px 10px",
                              borderRadius: "6px",
                              background:
                                i.status === "EMAIL_VERIFIED"
                                  ? "#f3e8ff"
                                  : i.status === "OTP_VERIFICATION_PENDING" || i.status === "PENDING"
                                  ? "#fffbe6"
                                  : i.status === "EMAIL_DELIVERY_ACCEPTED"
                                  ? "#e6f4ff"
                                  : i.status === "ACCEPTED"
                                  ? "#f6ffed"
                                  : i.status === "LOCKED"
                                  ? "#fff1f0"
                                  : "#f5f5f7",
                              color:
                                i.status === "EMAIL_VERIFIED"
                                  ? "#7e22ce"
                                  : i.status === "OTP_VERIFICATION_PENDING" || i.status === "PENDING"
                                  ? "#d4b106"
                                  : i.status === "EMAIL_DELIVERY_ACCEPTED"
                                  ? "#0071e3"
                                  : i.status === "ACCEPTED"
                                  ? "#389e0d"
                                  : i.status === "LOCKED"
                                  ? "#cf1322"
                                  : "#86868b",
                              border: `1px solid ${
                                i.status === "EMAIL_VERIFIED"
                                  ? "#e9d5ff"
                                  : i.status === "OTP_VERIFICATION_PENDING" || i.status === "PENDING"
                                  ? "#ffe58f"
                                  : i.status === "EMAIL_DELIVERY_ACCEPTED"
                                  ? "#91caff"
                                  : i.status === "ACCEPTED"
                                  ? "#b7eb8f"
                                  : i.status === "LOCKED"
                                  ? "#ffa39e"
                                  : "#d9d9d9"
                              }`,
                            }}
                          >
                            {i.status === "EMAIL_VERIFIED"
                              ? "Email Verified"
                              : i.status === "OTP_VERIFICATION_PENDING" || i.status === "PENDING"
                              ? "Verification Pending"
                              : i.status === "EMAIL_DELIVERY_ACCEPTED"
                              ? "Delivery Accepted"
                              : i.status === "ACCEPTED"
                              ? "Account Created"
                              : i.status === "LOCKED"
                              ? "Locked"
                              : i.status === "EXPIRED"
                              ? "Expired"
                              : i.status === "REVOKED"
                              ? "Revoked"
                              : i.status}
                          </span>
                        </td>
                        <td style={{ padding: "14px 16px", color: "var(--text-secondary)" }}>
                          {new Date(i.created_at).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </td>
                        <td style={{ padding: "14px 16px", color: "var(--text-secondary)" }}>
                          {new Date(i.expires_at).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </td>
                        <td style={{ padding: "14px 16px", textAlign: "right" }}>
                          {i.status === "PENDING" && (
                            <div style={{ display: "inline-flex", gap: "8px" }}>
                              <button
                                onClick={() => handleResend(i.id)}
                                style={{
                                  border: "1px solid var(--border-subtle)",
                                  background: "#ffffff",
                                  color: "var(--accent)",
                                  padding: "5px 10px",
                                  borderRadius: "var(--radius-sm)",
                                  fontSize: "12px",
                                  fontWeight: "600",
                                  cursor: "pointer",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <RefreshCw size={13} /> Resend
                              </button>
                              <button
                                onClick={() => setRevokeModalInv(i)}
                                style={{
                                  border: "1px solid #ffa39e",
                                  background: "#ffffff",
                                  color: "#cf1322",
                                  padding: "5px 10px",
                                  borderRadius: "var(--radius-sm)",
                                  fontSize: "12px",
                                  fontWeight: "600",
                                  cursor: "pointer",
                                }}
                              >
                                Revoke
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Invite User Modal */}
      {inviteModalOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
            backdropFilter: "blur(4px)",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "460px",
              background: "#ffffff",
              borderRadius: "16px",
              padding: "28px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.15)",
              position: "relative",
            }}
          >
            <button
              onClick={() => setInviteModalOpen(false)}
              style={{
                position: "absolute",
                top: "20px",
                right: "20px",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                color: "var(--text-tertiary)",
              }}
            >
              <X size={20} />
            </button>

            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
              <div
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "10px",
                  background: "rgba(0, 113, 227, 0.1)",
                  color: "var(--accent)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <UserPlus size={20} />
              </div>
              <h2 style={{ fontSize: "18px", fontWeight: "700" }}>Create User Account</h2>
            </div>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "20px" }}>
              Create a new user account directly. A temporary password will be generated for the user.
            </p>

            {inviteError && (
              <div
                style={{
                  padding: "10px 12px",
                  borderRadius: "6px",
                  background: "#fff1f0",
                  border: "1px solid #ffa39e",
                  color: "#e60000",
                  fontSize: "12.5px",
                  marginBottom: "16px",
                }}
              >
                {inviteError}
              </div>
            )}

            {createdTempPassword ? (
              <div
                style={{
                  background: "#f6ffed",
                  border: "1px solid #b7eb8f",
                  borderRadius: "10px",
                  padding: "18px",
                  marginBottom: "20px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    color: "#389e0d",
                    fontWeight: "600",
                    fontSize: "14.5px",
                    marginBottom: "8px",
                  }}
                >
                  <CheckCircle2 size={20} />
                  <span>Account Created Successfully</span>
                </div>
                <p style={{ fontSize: "12.5px", color: "var(--text-secondary)", marginBottom: "14px", lineHeight: "1.4" }}>
                  Provide these initial credentials to the user. The user will be required to create a new permanent password when logging in for the first time.
                </p>
                <div
                  style={{
                    background: "#ffffff",
                    border: "1px solid #d9f7be",
                    borderRadius: "8px",
                    padding: "12px",
                    fontSize: "13px",
                    fontFamily: "monospace",
                    marginBottom: "14px",
                    color: "var(--text-primary)",
                  }}
                >
                  <div><strong>Email:</strong> {inviteSuccessMsg?.replace("User account created successfully for ", "") || ""}</div>
                  <div style={{ marginTop: "4px" }}><strong>Temporary Password:</strong> <span style={{ background: "#feffe6", padding: "2px 6px", borderRadius: "4px", color: "#d48806", fontWeight: "700" }}>{createdTempPassword}</span></div>
                </div>
                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                  <button
                    onClick={() => {
                      const textToCopy = `Email: ${inviteSuccessMsg?.replace("User account created successfully for ", "") || ""}\nTemporary Password: ${createdTempPassword}`;
                      handleCopyUrl(textToCopy);
                    }}
                    className="btn btn-primary"
                    style={{ padding: "8px 14px", fontSize: "12.5px", display: "flex", alignItems: "center", gap: "6px" }}
                  >
                    {copiedUrl ? <Check size={14} /> : <Copy size={14} />}
                    <span>{copiedUrl ? "Copied Credentials" : "Copy Credentials"}</span>
                  </button>
                  <button
                    onClick={() => {
                      setInviteModalOpen(false);
                      setCreatedTempPassword(null);
                    }}
                    style={{
                      padding: "8px 14px",
                      fontSize: "12.5px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-subtle)",
                      background: "#ffffff",
                      cursor: "pointer",
                    }}
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSendInvite} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "600", marginBottom: "6px" }}>
                    User Full Name
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Rahul Sharma"
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      fontSize: "13px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-subtle)",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "600", marginBottom: "6px" }}>
                    Work Email Address *
                  </label>
                  <input
                    type="email"
                    placeholder="rahul@company.com"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      fontSize: "13px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-subtle)",
                    }}
                  />
                </div>

                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                    <label style={{ fontSize: "12px", fontWeight: "600" }}>Application Role</label>
                    <button
                      type="button"
                      onClick={() => { setShowAddRoleInput((p) => !p); setNewRoleName(""); setNewRoleError(null); }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        fontSize: "11px",
                        fontWeight: "600",
                        color: "var(--accent)",
                        background: "transparent",
                        border: "1px solid var(--accent)",
                        borderRadius: "5px",
                        padding: "3px 8px",
                        cursor: "pointer",
                      }}
                    >
                      <Plus size={11} />
                      Add Role
                    </button>
                  </div>

                  {showAddRoleInput && (
                    <div style={{ marginBottom: "10px", padding: "10px 12px", background: "#f0f7ff", borderRadius: "8px", border: "1px solid #bfdbfe" }}>
                      <p style={{ fontSize: "11.5px", color: "#1e40af", fontWeight: "600", marginBottom: "8px" }}>Create Custom Role</p>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        <input
                          type="text"
                          placeholder="e.g. Tax Accountant"
                          value={newRoleName}
                          onChange={(e) => { setNewRoleName(e.target.value); setNewRoleError(null); }}
                          style={{
                            flex: 1,
                            padding: "7px 10px",
                            fontSize: "12px",
                            borderRadius: "6px",
                            border: "1px solid #bfdbfe",
                            background: "#ffffff",
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const trimmed = newRoleName.trim();
                            if (!trimmed) { setNewRoleError("Role name cannot be empty."); return; }
                            const value = trimmed.toUpperCase().replace(/\s+/g, "_");
                            if (availableRoles.find((r) => r.value === value)) {
                              setNewRoleError("This role already exists.");
                              return;
                            }
                            setAvailableRoles((prev) => [...prev, { value, label: trimmed }]);
                            setSelectedInviteRole(value);
                            setNewRoleName("");
                            setShowAddRoleInput(false);
                          }}
                          className="btn btn-primary"
                          style={{ padding: "7px 12px", fontSize: "12px" }}
                        >
                          Add
                        </button>
                      </div>
                      {newRoleError && (
                        <p style={{ fontSize: "11px", color: "#e60000", marginTop: "5px" }}>{newRoleError}</p>
                      )}
                    </div>
                  )}

                  <select
                    value={selectedInviteRole}
                    onChange={(e) => setSelectedInviteRole(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      fontSize: "13px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-subtle)",
                      background: "#ffffff",
                      cursor: "pointer",
                    }}
                  >
                    {availableRoles.map((role) => (
                      <option key={role.value} value={role.value}>
                        {role.label}
                      </option>
                    ))}
                  </select>

                  {availableRoles.length > 2 && (
                    <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "4px" }}>
                      {availableRoles.filter((r) => !["FINANCE_USER", "FINANCE_ADMIN"].includes(r.value)).map((role) => (
                        <div
                          key={role.value}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "4px 8px",
                            background: "#f9fafb",
                            borderRadius: "5px",
                            border: "1px solid var(--border-subtle)",
                            fontSize: "11.5px",
                            color: "var(--text-secondary)",
                          }}
                        >
                          <span><strong>{role.label}</strong> <span style={{ opacity: 0.6 }}>({role.value})</span></span>
                          <button
                            type="button"
                            onClick={() => {
                              setAvailableRoles((prev) => prev.filter((r) => r.value !== role.value));
                              if (selectedInviteRole === role.value) setSelectedInviteRole("FINANCE_USER");
                            }}
                            style={{ background: "none", border: "none", cursor: "pointer", color: "#e60000", padding: "2px" }}
                            title="Remove role"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
                  <button
                    type="button"
                    onClick={() => setInviteModalOpen(false)}
                    style={{
                      padding: "8px 14px",
                      fontSize: "13px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-subtle)",
                      background: "#ffffff",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingInvite}
                    className="btn btn-primary"
                    style={{
                      padding: "8px 16px",
                      fontSize: "13px",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    {isSubmittingInvite && <Loader2 size={14} className="animate-spin" />}
                    <span>Create Account</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Deactivate User Confirmation Dialog */}
      {deactivateModalUser && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "420px",
              background: "#ffffff",
              borderRadius: "16px",
              padding: "24px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "12px",
                background: "#fff1f0",
                color: "#cf1322",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 16px",
              }}
            >
              <UserX size={24} />
            </div>
            <h3 style={{ fontSize: "17px", fontWeight: "700", marginBottom: "8px" }}>
              Deactivate {deactivateModalUser.full_name || deactivateModalUser.email}?
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "20px" }}>
              This will prevent the user from logging into Sakshi Finance. Their existing finance records, approvals, and audit history will remain intact.
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
              <button
                onClick={() => setDeactivateModalUser(null)}
                style={{
                  padding: "9px 16px",
                  fontSize: "13px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                  background: "#ffffff",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleDeactivate}
                disabled={actionLoading}
                style={{
                  padding: "9px 16px",
                  fontSize: "13px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: "#cf1322",
                  color: "#ffffff",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                {actionLoading ? "Deactivating..." : "Deactivate User"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reactivate User Confirmation Dialog */}
      {reactivateModalUser && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "420px",
              background: "#ffffff",
              borderRadius: "16px",
              padding: "24px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "12px",
                background: "#f6ffed",
                color: "#389e0d",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 16px",
              }}
            >
              <UserCheck size={24} />
            </div>
            <h3 style={{ fontSize: "17px", fontWeight: "700", marginBottom: "8px" }}>
              Reactivate {reactivateModalUser.full_name || reactivateModalUser.email}?
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "20px" }}>
              This will restore application access for this account.
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
              <button
                onClick={() => setReactivateModalUser(null)}
                style={{
                  padding: "9px 16px",
                  fontSize: "13px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                  background: "#ffffff",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleReactivate}
                disabled={actionLoading}
                style={{
                  padding: "9px 16px",
                  fontSize: "13px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: "#389e0d",
                  color: "#ffffff",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                {actionLoading ? "Reactivating..." : "Reactivate User"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Revoke Invitation Confirmation Dialog */}
      {revokeModalInv && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "420px",
              background: "#ffffff",
              borderRadius: "16px",
              padding: "24px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "12px",
                background: "#fff1f0",
                color: "#cf1322",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 16px",
              }}
            >
              <AlertTriangle size={24} />
            </div>
            <h3 style={{ fontSize: "17px", fontWeight: "700", marginBottom: "8px" }}>
              Revoke invitation for {revokeModalInv.email}?
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "20px" }}>
              The invitation token will immediately become invalid and cannot be accepted.
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
              <button
                onClick={() => setRevokeModalInv(null)}
                style={{
                  padding: "9px 16px",
                  fontSize: "13px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                  background: "#ffffff",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleRevoke}
                disabled={actionLoading}
                style={{
                  padding: "9px 16px",
                  fontSize: "13px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: "#cf1322",
                  color: "#ffffff",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                {actionLoading ? "Revoking..." : "Revoke Invitation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
