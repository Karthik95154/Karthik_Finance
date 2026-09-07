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
  Info,
} from "lucide-react";
import {
  listStagedDocuments,
  processStagedDocument,
  deleteStagedDocument,
  pollEmails,
  getInvoiceFileUrl,
  StagedDocument,
} from "@/lib/api";

const FIRST_POLL_KEY = "inbox_poll_confirmed";

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
  const [showFirstPollModal, setShowFirstPollModal] = useState(false);

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

  const runPoll = async () => {
    setIsPolling(true);
    setNotification(null);
    try {
      const summary = await pollEmails();
      setNotification({
        type: "success",
        message: `Checked ${summary.emails_checked} emails. Found ${summary.attachments_found} attachments. Added ${summary.new_documents} new invoices and skipped ${summary.duplicates} duplicates.`,
      });
      await loadDocuments();
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Email polling execution failed." });
    } finally {
      setIsPolling(false);
    }
  };

  const handlePoll = () => {
    const alreadyConfirmed = typeof window !== "undefined" && localStorage.getItem(FIRST_POLL_KEY) === "true";
    if (!alreadyConfirmed) {
      setShowFirstPollModal(true);
    } else {
      runPoll();
    }
  };

  const handleFirstPollConfirm = () => {
    localStorage.setItem(FIRST_POLL_KEY, "true");
    setShowFirstPollModal(false);
    runPoll();
  };

  const handleProcess = async (id: string) => {
    setProcessingIds((prev) => { const n = new Set(prev); n.add(id); return n; });
    try {
      await processStagedDocument(id);
      setNotification({ type: "success", message: "Invoice successfully sent to AI extraction pipeline." });
      setStagedDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Failed to trigger invoice extraction." });
    } finally {
      setProcessingIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this staged attachment?")) return;
    try {
      await deleteStagedDocument(id);
      setNotification({ type: "success", message: "Staged document deleted successfully." });
      setStagedDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      setNotification({ type: "error", message: err.message || "Failed to delete staged document." });
    }
  };

  const formatSize = (bytes: number | null | undefined) => {
    if (!bytes || bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatTime = (isoString: string | null) => {
    if (!isoString) return "-";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch { return isoString; }
  };

  return (
    <div className="container" style={{ maxWidth: "1000px", paddingTop: "40px", paddingBottom: "80px" }}>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "6px" }}>
            Staging Queue
          </h1>
          <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
            Review and trigger AI processing on incoming invoices ingested from corporate email.
          </p>
        </div>
        <button onClick={handlePoll} disabled={isPolling} className="btn btn-primary"
          style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <RefreshCw className={isPolling ? "animate-spin" : ""} size={16} />
          {isPolling ? "Checking..." : "Check Mail"}
        </button>
      </div>

      {/* Notification */}
      {notification && (
        <div style={{
          marginBottom: "24px", padding: "14px 18px", borderRadius: "var(--radius-sm)",
          background: notification.type === "success" ? "#ecfdf5" : "#fef2f2",
          border: `1px solid ${notification.type === "success" ? "#a7f3d0" : "#fca5a5"}`,
          color: notification.type === "success" ? "#065f46" : "#991b1b",
          display: "flex", alignItems: "center", gap: "10px", fontSize: "14.5px",
        }}>
          {notification.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span style={{ flex: 1 }}>{notification.message}</span>
          <button onClick={() => setNotification(null)} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}>
            <X size={16} />
          </button>
        </div>
      )}

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {isLoading ? (
          <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-secondary)" }}>
            <RefreshCw className="animate-spin" size={36} style={{ marginBottom: "16px", color: "var(--accent)" }} />
            <p>Loading staging queue...</p>
          </div>
        ) : stagedDocs.length === 0 ? (
          <div style={{ textAlign: "center", padding: "100px 40px", color: "var(--text-secondary)" }}>
            <Inbox size={48} style={{ marginBottom: "18px", strokeWidth: 1.5, color: "#cbd5e1" }} />
            <h3 style={{ fontSize: "16px", fontWeight: "600", color: "var(--text-primary)", marginBottom: "6px" }}>Queue is Empty</h3>
            <p style={{ fontSize: "13.5px", maxWidth: "360px", margin: "0 auto" }}>
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
                  <tr key={doc.id} style={{ borderBottom: "1px solid var(--border-subtle)", transition: "background 0.15s ease" }} className="hover-row">
                    <td style={{ padding: "18px 20px", verticalAlign: "top", maxWidth: "300px" }}>
                      <div style={{ fontWeight: "600", color: "var(--text-primary)", marginBottom: "4px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {doc.email_subject || "(No Subject)"}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-secondary)" }}>
                        <User size={12} /><span>{doc.email_sender}</span>
                      </div>
                    </td>
                    <td style={{ padding: "18px 20px", verticalAlign: "top" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "500", color: "var(--text-primary)", marginBottom: "4px" }}>
                        <FileText size={14} color="var(--accent)" /><span>{doc.file_name}</span>
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{formatSize(doc.file_size)} &bull; {doc.mime_type}</div>
                    </td>
                    <td style={{ padding: "18px 20px", verticalAlign: "top", color: "var(--text-secondary)", fontSize: "12.5px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <Clock size={12} /><span>{formatTime(doc.email_received_at || doc.created_at)}</span>
                      </div>
                    </td>
                    <td style={{ padding: "18px 20px", verticalAlign: "top", textAlign: "right" }}>
                      <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                        <button onClick={() => setPreviewDoc(doc)} className="btn btn-secondary"
                          style={{ padding: "6px 12px", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}>
                          <Eye size={12} />Preview
                        </button>
                        <button onClick={() => handleDelete(doc.id)} className="btn btn-secondary"
                          style={{ padding: "6px 12px", fontSize: "12px", color: "var(--danger)", display: "flex", alignItems: "center", gap: "4px" }}>
                          <Trash2 size={12} />Delete
                        </button>
                        <button onClick={() => handleProcess(doc.id)} disabled={processingIds.has(doc.id)} className="btn btn-primary"
                          style={{ padding: "6px 12px", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}>
                          {processingIds.has(doc.id)
                            ? <><RefreshCw size={12} className="animate-spin" />Queuing...</>
                            : <><Play size={12} />Process</>}
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

      {/* ── First-Poll Confirmation Modal ── */}
      {showFirstPollModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 2000,
          display: "flex", alignItems: "center", justifyContent: "center",
          backdropFilter: "blur(4px)", padding: "20px", animation: "fadeIn 0.18s ease-out",
        }}>
          <div style={{
            background: "#fff", borderRadius: "16px", width: "100%", maxWidth: "460px",
            boxShadow: "0 32px 64px -12px rgba(0,0,0,0.3)", overflow: "hidden",
            animation: "scaleUp 0.2s ease-out",
          }}>
            {/* Header */}
            <div style={{
              background: "linear-gradient(135deg,#1e40af 0%,#3b82f6 100%)",
              padding: "26px 28px 22px", position: "relative",
            }}>
              <button onClick={() => setShowFirstPollModal(false)} style={{
                position: "absolute", top: "14px", right: "14px",
                background: "rgba(255,255,255,0.2)", border: "none", borderRadius: "50%",
                width: "28px", height: "28px", display: "flex", alignItems: "center",
                justifyContent: "center", cursor: "pointer", color: "#fff",
              }}>
                <X size={13} />
              </button>
              <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "4px" }}>
                <div style={{
                  width: "40px", height: "40px", background: "rgba(255,255,255,0.2)",
                  borderRadius: "10px", display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Mail size={20} color="#fff" />
                </div>
                <div>
                  <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#fff", margin: 0 }}>Fetch Emails</h2>
                  <p style={{ fontSize: "12.5px", color: "rgba(255,255,255,0.75)", margin: 0 }}>First-time email scan</p>
                </div>
              </div>
            </div>

            {/* Body */}
            <div style={{ padding: "24px 28px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginBottom: "24px" }}>

                {/* Row 1 */}
                <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <div style={{ minWidth: "34px", height: "34px", background: "#eff6ff", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <Clock size={15} color="#3b82f6" />
                  </div>
                  <div>
                    <p style={{ fontSize: "13.5px", fontWeight: "600", color: "#1e293b", margin: "0 0 3px" }}>Initial scan — last 24 hours</p>
                    <p style={{ fontSize: "12.5px", color: "#64748b", margin: 0, lineHeight: 1.55 }}>
                      Since this is your first fetch, the system will scan emails received in the last 24 hours and extract invoice attachments.
                    </p>
                  </div>
                </div>

                {/* Row 2 */}
                <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <div style={{ minWidth: "34px", height: "34px", background: "#f0fdf4", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <RefreshCw size={15} color="#22c55e" />
                  </div>
                  <div>
                    <p style={{ fontSize: "13.5px", fontWeight: "600", color: "#1e293b", margin: "0 0 3px" }}>Automatic daily fetch at 7:00 AM</p>
                    <p style={{ fontSize: "12.5px", color: "#64748b", margin: 0, lineHeight: 1.55 }}>
                      After this first fetch, emails will be pulled automatically every morning at 7:00 AM — only new emails since the last scan.
                    </p>
                  </div>
                </div>

                {/* Row 3 */}
                <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <div style={{ minWidth: "34px", height: "34px", background: "#fefce8", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <Info size={15} color="#eab308" />
                  </div>
                  <div>
                    <p style={{ fontSize: "13.5px", fontWeight: "600", color: "#1e293b", margin: "0 0 3px" }}>Only invoices are saved</p>
                    <p style={{ fontSize: "12.5px", color: "#64748b", margin: 0, lineHeight: 1.55 }}>
                      Non-financial attachments are automatically discarded — only invoices, credit notes, and debit notes are stored.
                    </p>
                  </div>
                </div>

              </div>

              {/* Buttons */}
              <div style={{ display: "flex", gap: "10px" }}>
                <button onClick={() => setShowFirstPollModal(false)} className="btn btn-secondary"
                  style={{ flex: 1, padding: "11px", fontSize: "14px", fontWeight: "500" }}>
                  Cancel
                </button>
                <button onClick={handleFirstPollConfirm} className="btn btn-primary"
                  style={{
                    flex: 2, padding: "11px", fontSize: "14px", fontWeight: "600",
                    display: "flex", alignItems: "center", justifyContent: "center", gap: "8px",
                    background: "linear-gradient(135deg,#1e40af 0%,#3b82f6 100%)", border: "none",
                  }}>
                  <Mail size={15} />
                  Yes, Fetch Emails
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* File Preview Modal */}
      {previewDoc && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.5)", zIndex: 1000,
          display: "flex", alignItems: "center", justifyContent: "center",
          backdropFilter: "blur(2px)", padding: "20px",
        }}>
          <div style={{
            width: "100%", maxWidth: "800px", height: "90vh", background: "#fff",
            borderRadius: "var(--radius-md)", display: "flex", flexDirection: "column",
            overflow: "hidden", boxShadow: "0 25px 50px -12px rgba(0,0,0,0.25)",
            animation: "scaleUp 0.2s ease-out",
          }}>
            <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h4 style={{ fontWeight: "600", fontSize: "16px", color: "var(--text-primary)", marginBottom: "2px" }}>{previewDoc.file_name}</h4>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)" }}>Ingested from: "{previewDoc.email_subject}"</p>
              </div>
              <button onClick={() => setPreviewDoc(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", padding: "4px" }}>
                <X size={20} />
              </button>
            </div>
            <div style={{ flex: 1, backgroundColor: "#f1f3f4", position: "relative" }}>
              {previewDoc.file_name.toLowerCase().endsWith(".pdf") ? (
                <iframe src={getInvoiceFileUrl(previewDoc.id)} title="PDF Preview" style={{ width: "100%", height: "100%", border: "none" }} />
              ) : (
                <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", overflow: "auto", padding: "20px" }}>
                  <img src={getInvoiceFileUrl(previewDoc.id)} alt="Invoice Attachment" style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain", borderRadius: "4px" }} />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .hover-row:hover { background-color: #fafafa !important; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes scaleUp { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
      `}</style>
    </div>
  );
}
