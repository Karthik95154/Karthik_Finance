"use client";

import React, { useState, useEffect } from "react";
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

  // Preview Modal state
  const [previewDoc, setPreviewDoc] = useState<StagedDocument | null>(null);

  // Load staged documents
  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const docs = await listStagedDocuments();
      setStagedDocs(docs);
    } catch (err: any) {
      console.error(err);
      setNotification({
        type: "error",
        message: err.message || "Failed to load staging queue.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  // Clear notification banner after 5 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  // Check Mail / Poll emails handler
  const handlePoll = async () => {
    setIsPolling(true);
    setNotification(null);
    try {
      const summary = await pollEmails();
      setNotification({
        type: "success",
        message: `Checked ${summary.emails_checked} emails. Found ${summary.attachments_found} attachments. Added ${summary.new_documents} new invoices and skipped ${summary.duplicates} duplicates.`,
      });
      // Reload documents
      await loadDocuments();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Email polling execution failed.",
      });
    } finally {
      setIsPolling(false);
    }
  };

  // Process Document promotion handler
  const handleProcess = async (id: string) => {
    setProcessingIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });

    try {
      await processStagedDocument(id);
      setNotification({
        type: "success",
        message: "Invoice successfully sent to AI extraction pipeline.",
      });
      // Remove from view
      setStagedDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to trigger invoice extraction.",
      });
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  // Delete document handler
  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this staged attachment?")) {
      return;
    }
    try {
      await deleteStagedDocument(id);
      setNotification({
        type: "success",
        message: "Staged document deleted successfully.",
      });
      setStagedDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to delete staged document.",
      });
    }
  };

  // Format file size
  const formatSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  // Format timestamp
  const formatTime = (isoString: string | null) => {
    if (!isoString) return "-";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return isoString;
    }
  };

  return (
    <div className="container" style={{ maxWidth: "1000px", paddingTop: "40px", paddingBottom: "80px" }}>

      {/* Header Banner */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "6px" }}>
            📥 Staging Queue
          </h1>
          <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
            Review and trigger AI processing on incoming invoices ingested from corporate email.
          </p>
        </div>
        <button
          onClick={handlePoll}
          disabled={isPolling}
          className="btn btn-primary"
          style={{ display: "flex", alignItems: "center", gap: "8px" }}
        >
          <RefreshCw className={isPolling ? "animate-spin" : ""} size={16} />
          {isPolling ? "Checking..." : "Check Mail"}
        </button>
      </div>

      {/* Notifications */}
      {notification && (
        <div
          style={{
            marginBottom: "24px",
            padding: "14px 18px",
            borderRadius: "var(--radius-sm)",
            background: notification.type === "success" ? "#ecfdf5" : "#fef2f2",
            border: `1px solid ${notification.type === "success" ? "#a7f3d0" : "#fca5a5"}`,
            color: notification.type === "success" ? "#065f46" : "#991b1b",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            fontSize: "14.5px",
            animation: "fadeIn 0.2s ease-out",
          }}
        >
          {notification.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span style={{ flex: 1 }}>{notification.message}</span>
          <button
            onClick={() => setNotification(null)}
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Main Table Card */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {isLoading ? (
          <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-secondary)" }}>
            <RefreshCw className="animate-spin" size={36} style={{ marginBottom: "16px", color: "var(--accent)" }} />
            <p style={{ fontSize: "15px" }}>Loading staging queue...</p>
          </div>
        ) : stagedDocs.length === 0 ? (
          <div style={{ textAlign: "center", padding: "100px 40px", color: "var(--text-secondary)" }}>
            <Inbox size={48} style={{ marginBottom: "18px", strokeWidth: 1.5, color: "#cbd5e1" }} />
            <h3 style={{ fontSize: "16px", fontWeight: "600", color: "var(--text-primary)", marginBottom: "6px" }}>
              Queue is Empty
            </h3>
            <p style={{ fontSize: "13.5px", maxWidth: "360px", margin: "0 auto 24px" }}>
              No staged email attachments available. Click "Check Mail" above or verify email connection settings.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13.5px", textAlign: "left" }}>
              <thead>
                <tr style={{ background: "#fafafa", borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", fontWeight: "600" }}>
                  <th style={{ padding: "16px 20px" }}>Email Source</th>
                  <th style={{ padding: "16px 20px" }}>Attachment Details</th>
                  <th style={{ padding: "16px 20px" }}>Received</th>
                  <th style={{ padding: "16px 20px", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {stagedDocs.map((doc) => (
                  <tr
                    key={doc.id}
                    style={{
                      borderBottom: "1px solid var(--border-subtle)",
                      transition: "background 0.15s ease",
                    }}
                    className="hover-row"
                  >
                    <td style={{ padding: "18px 20px", verticalAlign: "top", maxWidth: "300px" }}>
                      <div style={{ fontWeight: "600", color: "var(--text-primary)", marginBottom: "4px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {doc.email_subject || "(No Subject)"}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-secondary)" }}>
                        <User size={12} />
                        <span>{doc.email_sender}</span>
                      </div>
                    </td>
                    <td style={{ padding: "18px 20px", verticalAlign: "top" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "500", color: "var(--text-primary)", marginBottom: "4px" }}>
                        <FileText size={14} color="var(--accent)" />
                        <span>{doc.file_name}</span>
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                        {formatSize(doc.file_size)} &bull; {doc.mime_type}
                      </div>
                    </td>
                    <td style={{ padding: "18px 20px", verticalAlign: "top", color: "var(--text-secondary)", fontSize: "12.5px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <Clock size={12} />
                        <span>{formatTime(doc.email_received_at || doc.created_at)}</span>
                      </div>
                    </td>
                    <td style={{ padding: "18px 20px", verticalAlign: "top", textAlign: "right" }}>
                      <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                        <button
                          onClick={() => setPreviewDoc(doc)}
                          className="btn btn-secondary"
                          style={{ padding: "6px 12px", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}
                          title="Preview original file"
                        >
                          <Eye size={12} />
                          Preview
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="btn btn-secondary"
                          style={{ padding: "6px 12px", fontSize: "12px", color: "var(--danger)", display: "flex", alignItems: "center", gap: "4px" }}
                          title="Delete from staging queue"
                        >
                          <Trash2 size={12} />
                          Delete
                        </button>
                        <button
                          onClick={() => handleProcess(doc.id)}
                          disabled={processingIds.has(doc.id)}
                          className="btn btn-primary"
                          style={{ padding: "6px 12px", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}
                          title="Promote to invoice pipeline"
                        >
                          {processingIds.has(doc.id) ? (
                            <>
                              <RefreshCw size={12} className="animate-spin" />
                              Queuing...
                            </>
                          ) : (
                            <>
                              <Play size={12} />
                              Process
                            </>
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

      {/* File Preview Overlay Modal */}
      {previewDoc && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.5)",
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
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
              animation: "scaleUp 0.2s ease-out",
            }}
          >
            {/* Modal Header */}
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
                <h4 style={{ fontWeight: "600", fontSize: "16px", color: "var(--text-primary)", marginBottom: "2px" }}>
                  {previewDoc.file_name}
                </h4>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  Ingested from email: "{previewDoc.email_subject}"
                </p>
              </div>
              <button
                onClick={() => setPreviewDoc(null)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--text-secondary)",
                  padding: "4px",
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Content - File Render */}
            <div style={{ flex: 1, backgroundColor: "#f1f3f4", position: "relative" }}>
              {previewDoc.file_name.toLowerCase().endsWith(".pdf") ? (
                <iframe
                  src={getInvoiceFileUrl(previewDoc.id)}
                  title="PDF Preview"
                  style={{ width: "100%", height: "100%", border: "none" }}
                />
              ) : (
                <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", overflow: "auto", padding: "20px" }}>
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

      {/* Styles */}
      <style jsx>{`
        .hover-row:hover {
          background-color: #fafafa !important;
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleUp {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>

    </div>
  );
}
