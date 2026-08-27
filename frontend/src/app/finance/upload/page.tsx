"use client";

import React, { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { uploadInvoice, UploadResponse } from "@/lib/api";
import { UploadCloud, FileText, CheckCircle2, AlertCircle, ArrowRight } from "lucide-react";

const MAX_SIZE_MB = 25;
const ALLOWED_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/jpg"];

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const validateAndSetFile = (file: File) => {
    setError(null);
    setUploadResult(null);

    if (!ALLOWED_TYPES.includes(file.type)) {
      setError("Please upload a valid PDF, PNG, or JPEG invoice file.");
      return;
    }

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File size exceeds the ${MAX_SIZE_MB}MB limit.`);
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setError(null);

    try {
      const res = await uploadInvoice(selectedFile);
      setUploadResult(res);
      // Automatically route to processing page after upload
      router.push(`/finance/invoices/${res.invoice_id}/processing`);
    } catch (err: any) {
      setError(err.message || "Failed to upload invoice.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: "680px", paddingTop: "60px", paddingBottom: "80px" }}>
      <div style={{ textAlign: "center", marginBottom: "36px" }}>
        <h1 style={{ fontSize: "32px", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "10px" }}>
          Upload Vendor Invoice
        </h1>
        <p style={{ fontSize: "16px", color: "var(--text-secondary)" }}>
          Store and prepare invoices for automated processing & accounting review.
        </p>
      </div>

      <div className="card" style={{ padding: "32px" }}>
        {!uploadResult ? (
          <>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${isDragging ? "var(--accent)" : "var(--border-strong)"}`,
                borderRadius: "var(--radius-md)",
                backgroundColor: isDragging ? "#f0f7ff" : "var(--bg-main)",
                padding: "48px 24px",
                textAlign: "center",
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                style={{ display: "none" }}
                onChange={handleFileChange}
              />

              <div style={{ display: "flex", justifyContent: "center", marginBottom: "16px" }}>
                <div
                  style={{
                    width: "56px",
                    height: "56px",
                    borderRadius: "50%",
                    background: "#ffffff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "var(--shadow-sm)",
                    color: isDragging ? "var(--accent)" : "var(--text-secondary)",
                  }}
                >
                  <UploadCloud size={28} />
                </div>
              </div>

              <p style={{ fontSize: "16px", fontWeight: "600", marginBottom: "6px" }}>
                {selectedFile ? selectedFile.name : "Drag and drop invoice file here"}
              </p>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "12px" }}>
                Supports PDF, PNG, or JPEG up to 25MB
              </p>

              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: "13px", pointerEvents: "none" }}
              >
                Browse File
              </button>
            </div>

            {selectedFile && (
              <div
                style={{
                  marginTop: "20px",
                  padding: "14px 18px",
                  borderRadius: "var(--radius-sm)",
                  background: "#f5f5f7",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <FileText size={18} color="var(--text-secondary)" />
                  <div>
                    <div style={{ fontSize: "14px", fontWeight: "500" }}>{selectedFile.name}</div>
                    <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  style={{ fontSize: "13px", color: "var(--danger)" }}
                >
                  Remove
                </button>
              </div>
            )}

            {error && (
              <div
                style={{
                  marginTop: "16px",
                  padding: "12px 16px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--danger-bg)",
                  color: "var(--danger)",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  fontSize: "14px",
                }}
              >
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            <div style={{ marginTop: "24px", display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={handleUpload}
                disabled={!selectedFile || isUploading}
                className="btn btn-primary"
                style={{ width: "100%", padding: "12px" }}
              >
                {isUploading ? "Uploading to Supabase Storage..." : "Upload Invoice"}
              </button>
            </div>
          </>
        ) : (
          <div style={{ textAlign: "center", padding: "16px 0" }}>
            <div
              style={{
                width: "56px",
                height: "56px",
                borderRadius: "50%",
                background: "var(--success-bg)",
                color: "var(--success)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 16px",
              }}
            >
              <CheckCircle2 size={32} />
            </div>

            <h2 style={{ fontSize: "20px", fontWeight: "600", marginBottom: "8px" }}>
              Invoice Uploaded Successfully
            </h2>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "24px" }}>
              File persisted in Supabase Storage with metadata recorded in PostgreSQL.
            </p>

            <div
              style={{
                background: "var(--bg-main)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)",
                padding: "16px",
                textAlign: "left",
                marginBottom: "24px",
                fontSize: "13px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "var(--text-secondary)" }}>Invoice ID:</span>
                <code style={{ fontWeight: "600" }}>{uploadResult.invoice_id}</code>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "var(--text-secondary)" }}>File Name:</span>
                <span>{uploadResult.file_name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "var(--text-secondary)" }}>Status:</span>
                <span className="badge badge-uploaded">{uploadResult.status}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-secondary)" }}>SHA-256 Hash:</span>
                <code style={{ fontSize: "11px" }}>{uploadResult.file_hash.substring(0, 16)}...</code>
              </div>
            </div>

            <div style={{ display: "flex", gap: "12px" }}>
              <button
                onClick={() => {
                  setSelectedFile(null);
                  setUploadResult(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                className="btn btn-secondary"
                style={{ flex: 1 }}
              >
                Upload Another
              </button>
              <button
                onClick={() => router.push(`/finance/invoices/${uploadResult.invoice_id}`)}
                className="btn btn-primary"
                style={{ flex: 1 }}
              >
                <span>View Invoice</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
