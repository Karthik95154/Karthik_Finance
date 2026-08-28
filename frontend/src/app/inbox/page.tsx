"use client";

import React, { useState, useEffect } from "react";
import AppShell from "@/components/AppShell";
import {
  Mail,
  RefreshCw,
  Trash2,
  Play,
  Eye,
  CheckCircle2,
  AlertCircle,
  FileText,
  Clock,
  User,
  Inbox,
  X,
} from "lucide-react";
import {
  listStagedDocuments,
  processStagedDocument,
  deleteStagedDocument,
  pollEmails,
  getInvoiceFileUrl,
  StagedDocument,
} from "@/lib/api";

export default function InboxPage() {
  const [stagedDocs, setStagedDocs] = useState<StagedDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isPolling, setIsPolling] = useState(false);
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [previewDoc, setPreviewDoc] = useState<StagedDocument | null>(null);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const docs = await listStagedDocuments();
      setStagedDocs(docs);
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Failed to load staging queue." });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { loadDocuments(); }, []);

  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  const handlePoll = async () => {
    setIsPolling(true);
    setNotification(null);
    try {
      const summary = await pollEmails();
      setNotification({
        type: "success",
        message: `Checked ${summary.emails_checked} emails — ${summary.new_documents} new invoices added, ${summary.duplicates} duplicates skipped.`,
      });
      await loadDocuments();
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Email polling failed." });
    } finally {
      setIsPolling(false);
    }
  };

  const handleProcess = async (id: string) => {
    setProcessingIds((prev) => { const n = new Set(prev); n.add(id); return n; });
    try {
      await processStagedDocument(id);
      setNotification({ type: "success", message: "Invoice sent to AI extraction pipeline." });
      setStagedDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Failed to trigger extraction." });
    } finally {
      setProcessingIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this staged attachment?")) return;
    try {
      await deleteStagedDocument(id);
      setNotification({ type: "success", message: "Staged document deleted." });
      setStagedDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Failed to delete." });
    }
  };

  const formatSize = (bytes: number) => {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const formatTime = (iso: string | null | undefined) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch { return iso; }
  };

  const checkMailAction = (
    <button
      onClick={handlePoll}
      disabled={isPolling}
      className="btn btn-primary"
      style={{ display: "flex", alignItems: "center", gap: "8px", padding: "7px 16px", fontSize: "13px" }}
    >
      <RefreshCw size={14} className={isPolling ? "animate-spin" : ""} />
      {isPolling ? "Checking..." : "Check Mail"}
    </button>
  );

  return (
    <AppShell title="Inbox" subtitle="Email Staging Queue" actions={checkMailAction}>

      {/* Notification Banner */}
      {notification && (
        <div
          style={{
            marginBottom: "20px",
            padding: "13px 16px",
            borderRadius: "var(--radius-sm)",
            background: notification.type === "success" ? "#ecfdf5" : "#fef2f2",
            border: `1px solid ${notification.type === "success" ? "#a7f3d0" : "#fca5a5"}`,
            color: notification.type === "success" ? "#065f46" : "#991b1b",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            fontSize: "13.5px",
          }}
        >
          {notification.type === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          <span style={{ flex: 1 }}>{notification.message}</span>
          <button onClick={() => setNotification(null)} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}>
            <X size={15} />
          </button>
        </div>
      )}

      {/* Stats Bar */}
      <div
        style={{
          display: "flex",
          gap: "1px",
          marginBottom: "20px",
          background: "#ffffff",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        {[
          { label: "Total Staged", value: stagedDocs.length, color: "var(--accent)" },
          { label: "PDFs", value: stagedDocs.filter((d) => d.mime_type === "application/pdf").length, color: "#7c3aed" },
          { label: "Images", value: stagedDocs.filter((d) => d.mime_type?.startsWith("image/")).length, color: "#0891b2" },
        ].map((stat) => (
          <div
            key={stat.label}
            style={{
              flex: 1,
              padding: "16px 20px",
              borderRight: "1px solid var(--border-subtle)",
            }}
          >
            <div style={{ fontSize: "22px", fontWeight: "700", color: stat.color, lineHeight: 1 }}>
              {isLoading ? "—" : stat.value}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px", fontWeight: "500" }}>
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {/* Main Table */}
      <div
        style={{
          background: "#ffffff",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        {isLoading ? (
          <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-secondary)" }}>
            <RefreshCw size={32} className="animate-spin" style={{ marginBottom: "16px", color: "var(--accent)" }} />
            <p style={{ fontSize: "14px" }}>Loading staging queue...</p>
          </div>
        ) : stagedDocs.length === 0 ? (
          <div style={{ textAlign: "center", padding: "80px 40px", color: "var(--text-secondary)" }}>
            <Inbox size={44} style={{ marginBottom: "16px", strokeWidth: 1.5, color: "#cbd5e1" }} />
            <h3 style={{ fontSize: "15px", fontWeight: "600", color: "var(--text-primary)", marginBottom: "6px" }}>
              Queue is Empty
            </h3>
            <p style={{ fontSize: "13px", maxWidth: "340px", margin: "0 auto 20px" }}>
              No staged documents. Click "Check Mail" to fetch new emails, or configure email in Integrations.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
              <thead>
                <tr
                  style={{
                    background: "#fafafa",
                    borderBottom: "1px solid var(--border-subtle)",
                    color: "var(--text-secondary)",
                    fontWeight: "600",
                    fontSize: "11px",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                  }}
                >
                  <th style={{ padding: "14px 20px" }}>Email Source</th>
                  <th style={{ padding: "14px 20px" }}>Attachment</th>
                  <th style={{ padding: "14px 20px" }}>Received</th>
                  <th style={{ padding: "14px 20px", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {stagedDocs.map((doc) => (
                  <tr
                    key={doc.id}
                    style={{ borderBottom: "1px solid var(--border-subtle)" }}
                    className="hover-row"
                  >
                    <td style={{ padding: "16px 20px", verticalAlign: "top", maxWidth: "280px" }}>
                      <div
                        style={{
                          fontWeight: "600",
                          color: "var(--text-primary)",
                          marginBottom: "4px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {doc.email_subject || "(No Subject)"}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "12px", color: "var(--text-secondary)" }}>
                        <User size={11} />
                        <span>{doc.email_sender}</span>
                      </div>
                    </td>
                    <td style={{ padding: "16px 20px", verticalAlign: "top" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "7px", fontWeight: "500", color: "var(--text-primary)", marginBottom: "4px" }}>
                        <FileText size={13} color="var(--accent)" />
                        <span>{doc.file_name}</span>
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                        {formatSize(doc.file_size || 0)} · {doc.mime_type}
                      </div>
                    </td>
                    <td style={{ padding: "16px 20px", verticalAlign: "top", color: "var(--text-secondary)", fontSize: "12px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                        <Clock size={11} />
                        <span>{formatTime(doc.email_received_at || doc.created_at)}</span>
                      </div>
                    </td>
                    <td style={{ padding: "16px 20px", verticalAlign: "top", textAlign: "right" }}>
                      <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                        <button
                          onClick={() => setPreviewDoc(doc)}
                          className="btn btn-secondary"
                          style={{ padding: "5px 10px", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}
                          title="Preview file"
                        >
                          <Eye size={12} /> Preview
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="btn btn-secondary"
                          style={{ padding: "5px 10px", fontSize: "12px", color: "#dc2626", display: "flex", alignItems: "center", gap: "4px" }}
                          title="Delete from queue"
                        >
                          <Trash2 size={12} />
                        </button>
                        <button
                          onClick={() => handleProcess(doc.id)}
                          disabled={processingIds.has(doc.id)}
                          className="btn btn-primary"
                          style={{ padding: "5px 12px", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}
                          title="Send to AI pipeline"
                        >
                          {processingIds.has(doc.id) ? (
                            <><RefreshCw size={11} className="animate-spin" /> Queuing...</>
                          ) : (
                            <><Play size={11} /> Process</>
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* File Preview Modal */}
      {previewDoc && (
        <div
          style={{
            position: "fixed",
            top: 0, left: 0, right: 0, bottom: 0,
            background: "rgba(0,0,0,0.5)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backdropFilter: "blur(2px)",
            padding: "20px",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "800px",
              height: "90vh",
              background: "#ffffff",
              borderRadius: "var(--radius-md)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              boxShadow: "0 25px 50px -12px rgba(0,0,0,0.25)",
            }}
          >
            <div
              style={{
                padding: "16px 24px",
                borderBottom: "1px solid var(--border-subtle)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <h4 style={{ fontWeight: "600", fontSize: "15px", color: "var(--text-primary)", marginBottom: "2px" }}>
                  {previewDoc.file_name}
                </h4>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  From: {previewDoc.email_subject}
                </p>
              </div>
              <button
                onClick={() => setPreviewDoc(null)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", padding: "4px" }}
              >
                <X size={20} />
              </button>
            </div>
            <div style={{ flex: 1, backgroundColor: "#f1f3f4", position: "relative" }}>
              {previewDoc.file_name.toLowerCase().endsWith(".pdf") ? (
                <iframe
                  src={getInvoiceFileUrl(previewDoc.id)}
                  title="PDF Preview"
                  style={{ width: "100%", height: "100%", border: "none" }}
                />
              ) : (
                <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}>
                  <img
                    src={getInvoiceFileUrl(previewDoc.id)}
                    alt="Invoice Attachment"
                    style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain", borderRadius: "4px" }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .hover-row:hover { background-color: #fafafa !important; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
      `}</style>
    </AppShell>
  );
}
