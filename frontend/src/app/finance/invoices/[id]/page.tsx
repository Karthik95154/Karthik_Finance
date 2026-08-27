"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getInvoice,
  getInvoiceFileUrl,
  updateInvoiceExtraction,
  triggerAccountingCategorization,
  listInvoices,
  Invoice,
  InvoiceListItem,
  ExtractedInvoiceData,
  LineItem,
  BankDetails,
  RawVlmOutput,
  AccountingOutput,
  AccountingLineItem,
  TdsResult,
} from "@/lib/api";
import {
  ArrowLeft,
  FileText,
  ExternalLink,
  Plus,
  Trash2,
  Save,
  CheckCircle2,
  Clock,
  Send,
  Check,
  X,
  Layers,
  Building2,
  User,
  CreditCard,
  Receipt,
  FileSpreadsheet,
  AlertCircle,
  BookOpen,
  Scale,
  RefreshCw,
} from "lucide-react";

// Helper to extract or derive invoice-level CGST/SGST/IGST amounts from Qwen3-VL extraction
function extractOrDeriveTax(
  extracted: ExtractedInvoiceData,
  taxType: "cgst" | "sgst" | "igst"
): number | null {
  // 1. Direct explicit top-level values if already present
  const direct =
    extracted[taxType] ??
    extracted[`${taxType}_amount` as keyof ExtractedInvoiceData];
  if (typeof direct === "number") return direct;
  if (typeof direct === "string" && !isNaN(parseFloat(direct))) return parseFloat(direct);

  // 2. Derive by summing corresponding line_items[].cgst_amount / sgst_amount / igst_amount
  const lineKey = `${taxType}_amount` as keyof LineItem;
  const lineAmounts: number[] = [];
  if (Array.isArray(extracted.line_items)) {
    for (const item of extracted.line_items) {
      const val = item[lineKey];
      if (val !== null && val !== undefined && val !== "") {
        const num = typeof val === "number" ? val : parseFloat(String(val));
        if (!isNaN(num)) {
          lineAmounts.push(num);
        }
      }
    }
  }
  if (lineAmounts.length > 0) {
    const sum = lineAmounts.reduce((a, b) => a + b, 0);
    return Math.round(sum * 100) / 100;
  }

  // 3. Search inside additional_fields / tax_details structures
  const af = extracted.additional_fields;
  if (af && typeof af === "object") {
    const upper = taxType.toUpperCase();
    const candidates = [
      af[taxType],
      af[upper],
      af[`${taxType}_amount`],
      af[`${upper}_AMOUNT`],
      af[`${taxType}_total`],
      af[`${upper}_TOTAL`],
      af.tax_details?.output_tax?.[taxType],
      af.tax_details?.output_tax?.[upper],
      af.tax_details?.tax_payable?.[taxType],
      af.tax_details?.tax_payable?.[upper],
      af.tax_details?.[taxType],
      af.tax_details?.[upper],
      af.tax_details?.[`${taxType}_amount`],
      af.tax_details?.[`${upper}_AMOUNT`],
    ];
    for (const cand of candidates) {
      if (typeof cand === "number") return cand;
      if (typeof cand === "string" && !isNaN(parseFloat(cand))) return parseFloat(cand);
    }
  }

  return null;
}

export default function InvoiceWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const invoiceId = params?.id as string;

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [workflowInvoices, setWorkflowInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isCategorizing, setIsCategorizing] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Editable form state
  const [formData, setFormData] = useState<ExtractedInvoiceData>({});
  const [accountingData, setAccountingData] = useState<AccountingOutput>({});
  const [additionalFieldsText, setAdditionalFieldsText] = useState<string>("");

  useEffect(() => {
    if (!invoiceId) return;

    async function loadData() {
      try {
        setLoading(true);
        const [invData, listData] = await Promise.all([
          getInvoice(invoiceId),
          listInvoices().catch(() => []),
        ]);

        setInvoice(invData);
        setWorkflowInvoices(listData);

        // If still in initial stages, route to processing page
        if (
          invData.status === "PENDING" ||
          invData.status === "PROCESSING_VLM" ||
          invData.status === "PROCESSING_ACCOUNTING"
        ) {
          router.push(`/finance/invoices/${invoiceId}/processing`);
          return;
        }

        // Initialize form state from current_vlm_output (edited) or raw_vlm_output (initial)
        const vlmOutput = invData.current_vlm_output || invData.raw_vlm_output || {};
        const extracted: ExtractedInvoiceData = vlmOutput.data ? { ...vlmOutput.data } : {};

        // Extract or derive CGST, SGST, IGST from explicit values, line item sums, or tax structures
        if (extracted.cgst === undefined && extracted.cgst_amount === undefined) {
          const derived = extractOrDeriveTax(extracted, "cgst");
          extracted.cgst = derived;
          extracted.cgst_amount = derived;
        }
        if (extracted.sgst === undefined && extracted.sgst_amount === undefined) {
          const derived = extractOrDeriveTax(extracted, "sgst");
          extracted.sgst = derived;
          extracted.sgst_amount = derived;
        }
        if (extracted.igst === undefined && extracted.igst_amount === undefined) {
          const derived = extractOrDeriveTax(extracted, "igst");
          extracted.igst = derived;
          extracted.igst_amount = derived;
        }

        if (!extracted.line_items) extracted.line_items = [];
        if (!extracted.bank_details) extracted.bank_details = {};

        setFormData(extracted);
        setAdditionalFieldsText(
          extracted.additional_fields
            ? JSON.stringify(extracted.additional_fields, null, 2)
            : ""
        );

        // Initialize accounting data from current_accounting_output or accounting_output
        const accOutput =
          invData.current_accounting_output || invData.accounting_output || {};
        setAccountingData(accOutput);
      } catch (err: any) {
        setError(err.message || "Failed to load invoice details.");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [invoiceId, router]);

  const fileUrl = invoiceId ? getInvoiceFileUrl(invoiceId) : "";
  const isPdf = invoice?.mime_type === "application/pdf";

  // Form update helpers
  const handleFieldChange = (field: keyof ExtractedInvoiceData, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleBankChange = (field: keyof BankDetails, value: string) => {
    setFormData((prev) => ({
      ...prev,
      bank_details: {
        ...(prev.bank_details || {}),
        [field]: value,
      },
    }));
  };

  const handleLineItemChange = (
    index: number,
    field: keyof LineItem,
    value: any
  ) => {
    setFormData((prev) => {
      const items = [...(prev.line_items || [])];
      items[index] = { ...items[index], [field]: value };
      return { ...prev, line_items: items };
    });
  };

  const addLineItem = () => {
    setFormData((prev) => ({
      ...prev,
      line_items: [
        ...(prev.line_items || []),
        {
          description: "",
          hsn_code: "",
          quantity: 1,
          unit_price: 0,
          discount: 0,
          taxable_amount: 0,
          cgst_rate: 0,
          cgst_amount: 0,
          sgst_rate: 0,
          sgst_amount: 0,
          igst_rate: 0,
          igst_amount: 0,
          total: 0,
        },
      ],
    }));
  };

  const removeLineItem = (index: number) => {
    setFormData((prev) => {
      const items = [...(prev.line_items || [])];
      items.splice(index, 1);
      return { ...prev, line_items: items };
    });
  };

  // Accounting classification line item editing
  const handleAccountingItemChange = (
    index: number,
    field: keyof AccountingLineItem,
    value: any
  ) => {
    setAccountingData((prev) => {
      const list = [...(prev.accounting || [])];
      if (list[index]) {
        list[index] = { ...list[index], [field]: value };
      }
      return { ...prev, accounting: list };
    });
  };

  // Trigger Stage 3 Qwen3-4B Accounting on current invoice data without rerun VLM
  const handleRunAccounting = async () => {
    try {
      setIsCategorizing(true);
      setError(null);
      await triggerAccountingCategorization(invoiceId);
      // Route to processing screen which polls until completed
      router.push(`/finance/invoices/${invoiceId}/processing`);
    } catch (err: any) {
      setError(err.message || "Failed to trigger accounting reasoning.");
      setIsCategorizing(false);
    }
  };

  // Save changes handler (persists both current VLM data and accounting classifications)
  const handleSaveChanges = async () => {
    try {
      setIsSaving(true);
      setError(null);
      setSaveSuccess(false);

      let parsedAdditional = formData.additional_fields || {};
      if (additionalFieldsText.trim()) {
        try {
          parsedAdditional = JSON.parse(additionalFieldsText);
        } catch {
          parsedAdditional = { raw_notes: additionalFieldsText };
        }
      }

      const updatedVlmPayload: RawVlmOutput = {
        ...(invoice?.current_vlm_output || invoice?.raw_vlm_output || {}),
        data: {
          ...formData,
          additional_fields: parsedAdditional,
        },
      };

      const updated = await updateInvoiceExtraction(
        invoiceId,
        updatedVlmPayload,
        accountingData
      );
      setInvoice(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to save changes.");
    } finally {
      setIsSaving(false);
    }
  };

  // Dummy action buttons notice
  const handleDummyAction = (actionName: string) => {
    setActionNotice(
      `"${actionName}" action triggered (Stage 3 Dummy UI). Real accounting sync will activate in later stages.`
    );
    setTimeout(() => setActionNotice(null), 4000);
  };

  // Categorized invoice workflow lists
  const incomingInvoices = workflowInvoices.filter(
    (inv) =>
      inv.status === "PENDING" ||
      inv.status === "PROCESSING_VLM" ||
      inv.status === "PROCESSING_ACCOUNTING"
  );
  const extractedInvoices = workflowInvoices.filter(
    (inv) => inv.status === "COMPLETED"
  );

  const accountingLines: AccountingLineItem[] =
    accountingData.accounting || [];
  const tdsResult: TdsResult | undefined = accountingData.tds || undefined;

  return (
    <div style={{ maxWidth: "1600px", margin: "0 auto", padding: "16px 24px 60px" }}>
      {/* Top Header / Status bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
          paddingBottom: "12px",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button
            onClick={() => router.push("/finance/upload")}
            className="btn btn-secondary"
            style={{ padding: "6px 12px", fontSize: "13px" }}
          >
            <ArrowLeft size={14} />
            <span>Upload New</span>
          </button>
          <div>
            <span style={{ fontSize: "16px", fontWeight: "700", letterSpacing: "-0.02em" }}>
              {formData.invoice_number ? `Invoice #${formData.invoice_number}` : invoice?.file_name}
            </span>
            {formData.vendor_name && (
              <span style={{ fontSize: "13px", color: "var(--text-secondary)", marginLeft: "8px" }}>
                · {formData.vendor_name}
              </span>
            )}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {invoice?.accounting_confidence !== null && invoice?.accounting_confidence !== undefined && (
            <span className="badge badge-uploaded" style={{ fontSize: "12px", color: "var(--accent)" }}>
              COA Confidence: {Math.round(invoice.accounting_confidence * 100)}%
            </span>
          )}
          <span
            className={`badge ${invoice?.status === "COMPLETED"
                ? "badge-success"
                : invoice?.status === "FAILED"
                  ? "badge-danger"
                  : "badge-uploaded"
              }`}
          >
            {invoice?.status === "COMPLETED" ? "Qwen3-VL + Qwen3-4B Ready" : invoice?.status}
          </span>
        </div>
      </div>

      {actionNotice && (
        <div
          style={{
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            color: "#1e40af",
            padding: "10px 16px",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <AlertCircle size={16} />
          <span>{actionNotice}</span>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: "100px 0" }}>
          <p style={{ color: "var(--text-secondary)", fontSize: "15px" }}>
            Loading invoice workspace...
          </p>
        </div>
      ) : error && !invoice ? (
        <div className="card" style={{ textAlign: "center", padding: "60px 24px" }}>
          <p style={{ color: "var(--danger)", fontSize: "16px", marginBottom: "16px" }}>{error}</p>
          <button onClick={() => router.push("/finance/upload")} className="btn btn-secondary">
            Return to Upload
          </button>
        </div>
      ) : invoice ? (
        <>
          {/* ==================================================== */}
          {/* TOP: TWO-COLUMN INVOICE WORKSPACE (INDEPENDENT SCROLL) */}
          {/* ==================================================== */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(420px, 48%) minmax(480px, 52%)",
              gap: "20px",
              height: "calc(100vh - 150px)",
              minHeight: "650px",
              marginBottom: "40px",
            }}
          >
            {/* ---------------------------------------------------- */}
            {/* TOP LEFT: ORIGINAL INVOICE VIEWER */}
            {/* ---------------------------------------------------- */}
            <div
              className="card"
              style={{
                display: "flex",
                flexDirection: "column",
                padding: "16px",
                height: "100%",
                overflow: "hidden",
              }}
            >
              {/* Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  paddingBottom: "12px",
                  borderBottom: "1px solid var(--border-subtle)",
                  marginBottom: "12px",
                }}
              >
                <div>
                  <div style={{ fontSize: "11px", fontWeight: "700", letterSpacing: "0.06em", color: "var(--text-secondary)", textTransform: "uppercase" }}>
                    Invoice Preview
                  </div>
                  <div style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "340px" }}>
                    {invoice.file_name}
                  </div>
                </div>

                <a
                  href={fileUrl}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    fontSize: "12px",
                    color: "var(--accent)",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    fontWeight: "500",
                  }}
                >
                  Open in new tab <ExternalLink size={13} />
                </a>
              </div>

              {/* Document Container with independent vertical scroll */}
              <div
                style={{
                  flex: 1,
                  backgroundColor: "#f5f5f7",
                  borderRadius: "var(--radius-sm)",
                  overflowY: "auto",
                  position: "relative",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                {isPdf ? (
                  <iframe
                    src={fileUrl}
                    style={{ width: "100%", height: "100%", border: "none" }}
                    title="Invoice PDF Preview"
                  />
                ) : (
                  <div
                    style={{
                      width: "100%",
                      minHeight: "100%",
                      display: "flex",
                      alignItems: "flex-start",
                      justifyContent: "center",
                      padding: "16px",
                    }}
                  >
                    <img
                      src={fileUrl}
                      alt={invoice.file_name}
                      style={{
                        maxWidth: "100%",
                        height: "auto",
                        borderRadius: "4px",
                        boxShadow: "var(--shadow-sm)",
                      }}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* ---------------------------------------------------- */}
            {/* TOP RIGHT: AI EXTRACTION REVIEW (LONG FORM WORKSPACE) */}
            {/* ---------------------------------------------------- */}
            <div
              className="card"
              style={{
                display: "flex",
                flexDirection: "column",
                padding: "0",
                height: "100%",
                overflow: "hidden",
              }}
            >
              {/* Review Panel Header with Action Buttons */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "16px 20px",
                  borderBottom: "1px solid var(--border-subtle)",
                  background: "#ffffff",
                  position: "sticky",
                  top: 0,
                  zIndex: 10,
                }}
              >
                <div>
                  <div style={{ fontSize: "11px", fontWeight: "700", letterSpacing: "0.06em", color: "var(--text-secondary)", textTransform: "uppercase" }}>
                    AI Extraction Review
                  </div>
                  <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-primary)" }}>
                    Final Invoice & Accounting Workspace
                  </div>
                </div>

                {/* Top Right Action Buttons: Reject, Approve, Export */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button
                    type="button"
                    onClick={() => handleDummyAction("Reject")}
                    className="btn btn-secondary"
                    style={{
                      padding: "6px 12px",
                      fontSize: "12px",
                      color: "var(--danger)",
                      borderColor: "var(--border-subtle)",
                    }}
                  >
                    <X size={14} />
                    <span>Reject</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDummyAction("Approve")}
                    className="btn btn-secondary"
                    style={{
                      padding: "6px 12px",
                      fontSize: "12px",
                      color: "var(--success)",
                      borderColor: "var(--border-subtle)",
                    }}
                  >
                    <Check size={14} />
                    <span>Approve</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDummyAction("Export")}
                    className="btn btn-secondary"
                    style={{
                      padding: "6px 12px",
                      fontSize: "12px",
                      color: "var(--accent)",
                      borderColor: "var(--border-subtle)",
                    }}
                  >
                    <Send size={14} />
                    <span>Export</span>
                  </button>
                </div>
              </div>

              {/* Independently Scrollable Form Workspace */}
              <div
                style={{
                  flex: 1,
                  overflowY: "auto",
                  padding: "20px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "24px",
                }}
              >
                {/* 1. INVOICE INFORMATION */}
                <section>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <Receipt size={16} color="var(--accent)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      1. Invoice Information
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px" }}>
                    <div>
                      <label className="form-label">Invoice Number</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.invoice_number ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("invoice_number", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Invoice Date</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.invoice_date ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("invoice_date", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Due Date</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.due_date ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("due_date", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">PO Number</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.po_number ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("po_number", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Place of Supply</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.place_of_supply ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("place_of_supply", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Currency</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.currency ?? "INR"}
                        placeholder="INR"
                        onChange={(e) => handleFieldChange("currency", e.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {/* 2. VENDOR / BILL FROM */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <Building2 size={16} color="var(--text-secondary)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      2. Vendor / Bill From
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Vendor Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_name ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("vendor_name", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Vendor GSTIN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_gstin ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("vendor_gstin", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Vendor PAN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_pan ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("vendor_pan", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Vendor CIN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_cin ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("vendor_cin", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Vendor Phone</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_phone ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("vendor_phone", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Vendor Email</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_email ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("vendor_email", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Vendor Address</label>
                      <textarea
                        className="form-input"
                        rows={2}
                        value={formData.vendor_address ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("vendor_address", e.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {/* 3. CUSTOMER / BILL TO */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <User size={16} color="var(--text-secondary)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      3. Customer / Bill To
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Customer Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.customer_name ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("customer_name", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Customer GSTIN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.customer_gstin ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("customer_gstin", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Customer PAN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.customer_pan ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("customer_pan", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Customer Address</label>
                      <textarea
                        className="form-input"
                        rows={2}
                        value={formData.customer_address ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("customer_address", e.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {/* 4. LINE ITEMS */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Layers size={16} color="var(--accent)" />
                      <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                        4. Line Items
                      </h3>
                      <span className="badge badge-uploaded" style={{ fontSize: "11px" }}>
                        {formData.line_items?.length || 0} items
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={addLineItem}
                      className="btn btn-secondary"
                      style={{ padding: "4px 10px", fontSize: "12px" }}
                    >
                      <Plus size={13} />
                      <span>Add Item Row</span>
                    </button>
                  </div>

                  <div
                    style={{
                      overflowX: "auto",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-sm)",
                      background: "#ffffff",
                    }}
                  >
                    <table style={{ width: "100%", minWidth: "950px", borderCollapse: "collapse", fontSize: "12px" }}>
                      <thead>
                        <tr style={{ background: "#f9f9fb", borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", textAlign: "left" }}>
                          <th style={{ padding: "8px 6px", width: "30px" }}>#</th>
                          <th style={{ padding: "8px 6px", minWidth: "160px" }}>Description</th>
                          <th style={{ padding: "8px 6px", width: "80px" }}>HSN/SAC</th>
                          <th style={{ padding: "8px 6px", width: "60px" }}>Qty</th>
                          <th style={{ padding: "8px 6px", width: "80px" }}>Unit Price</th>
                          <th style={{ padding: "8px 6px", width: "70px" }}>Discount</th>
                          <th style={{ padding: "8px 6px", width: "80px" }}>Taxable</th>
                          <th style={{ padding: "8px 6px", width: "60px" }}>CGST %</th>
                          <th style={{ padding: "8px 6px", width: "70px" }}>CGST Amt</th>
                          <th style={{ padding: "8px 6px", width: "60px" }}>SGST %</th>
                          <th style={{ padding: "8px 6px", width: "70px" }}>SGST Amt</th>
                          <th style={{ padding: "8px 6px", width: "60px" }}>IGST %</th>
                          <th style={{ padding: "8px 6px", width: "70px" }}>IGST Amt</th>
                          <th style={{ padding: "8px 6px", width: "90px" }}>Total</th>
                          <th style={{ padding: "8px 6px", width: "36px" }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {formData.line_items && formData.line_items.length > 0 ? (
                          formData.line_items.map((item, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                              <td style={{ padding: "6px", color: "var(--text-tertiary)", textAlign: "center" }}>
                                {idx + 1}
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="text"
                                  className="table-input"
                                  value={item.description ?? ""}
                                  placeholder="Description"
                                  onChange={(e) => handleLineItemChange(idx, "description", e.target.value)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="text"
                                  className="table-input"
                                  value={item.hsn_code ?? ""}
                                  placeholder="HSN"
                                  onChange={(e) => handleLineItemChange(idx, "hsn_code", e.target.value)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.quantity ?? ""}
                                  placeholder="1"
                                  onChange={(e) => handleLineItemChange(idx, "quantity", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.unit_price ?? ""}
                                  placeholder="0.00"
                                  onChange={(e) => handleLineItemChange(idx, "unit_price", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.discount ?? ""}
                                  placeholder="0"
                                  onChange={(e) => handleLineItemChange(idx, "discount", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.taxable_amount ?? ""}
                                  placeholder="0.00"
                                  onChange={(e) => handleLineItemChange(idx, "taxable_amount", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.cgst_rate ?? ""}
                                  placeholder="0%"
                                  onChange={(e) => handleLineItemChange(idx, "cgst_rate", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.cgst_amount ?? ""}
                                  placeholder="0.00"
                                  onChange={(e) => handleLineItemChange(idx, "cgst_amount", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.sgst_rate ?? ""}
                                  placeholder="0%"
                                  onChange={(e) => handleLineItemChange(idx, "sgst_rate", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.sgst_amount ?? ""}
                                  placeholder="0.00"
                                  onChange={(e) => handleLineItemChange(idx, "sgst_amount", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.igst_rate ?? ""}
                                  placeholder="0%"
                                  onChange={(e) => handleLineItemChange(idx, "igst_rate", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  value={item.igst_amount ?? ""}
                                  placeholder="0.00"
                                  onChange={(e) => handleLineItemChange(idx, "igst_amount", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="number"
                                  className="table-input"
                                  style={{ fontWeight: "600" }}
                                  value={item.total ?? ""}
                                  placeholder="0.00"
                                  onChange={(e) => handleLineItemChange(idx, "total", parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td style={{ padding: "6px", textAlign: "center" }}>
                                <button
                                  type="button"
                                  onClick={() => removeLineItem(idx)}
                                  style={{ background: "none", border: "none", color: "var(--text-tertiary)", cursor: "pointer", padding: "4px" }}
                                  title="Remove item"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={15} style={{ padding: "20px", textAlign: "center", color: "var(--text-secondary)" }}>
                              No line items extracted. Click "+ Add Item Row" to add.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>

                {/* 5. PAYMENT & BANK DETAILS */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <CreditCard size={16} color="var(--text-secondary)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      5. Payment & Bank Details
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Payment Terms</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.payment_terms ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleFieldChange("payment_terms", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Account Holder Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.account_holder_name ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleBankChange("account_holder_name", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Bank Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.bank_name ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleBankChange("bank_name", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Account Number</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.account_number ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleBankChange("account_number", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">IFSC Code</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.ifsc_code ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleBankChange("ifsc_code", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Branch</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.branch ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleBankChange("branch", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">UPI ID</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.upi_id ?? ""}
                        placeholder="Not provided"
                        onChange={(e) => handleBankChange("upi_id", e.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {/* 6. TAX DETAILS */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <Receipt size={16} color="var(--text-secondary)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      6. Tax Details
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px" }}>
                    <div>
                      <label className="form-label">Total Tax Amount</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.tax_total ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("tax_total", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                  </div>
                </section>

                {/* 7. FINANCIAL TOTALS */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <FileSpreadsheet size={16} color="var(--accent)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      7. Financial Totals
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div>
                      <label className="form-label">Subtotal</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.subtotal ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("subtotal", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                    <div>
                      <label className="form-label">Discount Total</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.discount_total ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("discount_total", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                    <div>
                      <label className="form-label">CGST</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.cgst_amount ?? formData.cgst ?? ""}
                        placeholder="0.00"
                        onChange={(e) => {
                          const val = e.target.value === "" ? null : parseFloat(e.target.value);
                          handleFieldChange("cgst_amount", val);
                          handleFieldChange("cgst", val);
                        }}
                      />
                    </div>
                    <div>
                      <label className="form-label">SGST</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.sgst_amount ?? formData.sgst ?? ""}
                        placeholder="0.00"
                        onChange={(e) => {
                          const val = e.target.value === "" ? null : parseFloat(e.target.value);
                          handleFieldChange("sgst_amount", val);
                          handleFieldChange("sgst", val);
                        }}
                      />
                    </div>
                    <div>
                      <label className="form-label">IGST</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.igst_amount ?? formData.igst ?? ""}
                        placeholder="0.00"
                        onChange={(e) => {
                          const val = e.target.value === "" ? null : parseFloat(e.target.value);
                          handleFieldChange("igst_amount", val);
                          handleFieldChange("igst", val);
                        }}
                      />
                    </div>
                    <div>
                      <label className="form-label">Total Tax Amount (Tax Total)</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.tax_total ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("tax_total", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                    <div>
                      <label className="form-label">Shipping Charges</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.shipping_charges ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("shipping_charges", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                    <div>
                      <label className="form-label">Other Charges</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.other_charges ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("other_charges", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Round Off</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.round_off ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("round_off", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label" style={{ fontWeight: "700" }}>Total Amount (Grand Total)</label>
                      <input
                        type="number"
                        className="form-input"
                        style={{ fontSize: "16px", fontWeight: "700", color: "var(--accent)" }}
                        value={formData.total_amount ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("total_amount", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                  </div>
                </section>

                {/* 8. ACCOUNTING CLASSIFICATION (STAGE 3 QWEN3-4B RESULT) */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <BookOpen size={16} color="var(--accent)" />
                      <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                        8. Accounting Classification (Qwen3-4B)
                      </h3>
                      {accountingLines.length > 0 && (
                        <span className="badge badge-success" style={{ fontSize: "11px" }}>
                          {accountingLines.length} classified
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={handleRunAccounting}
                      disabled={isCategorizing}
                      className="btn btn-secondary"
                      style={{ padding: "4px 10px", fontSize: "12px" }}
                      title="Send current invoice JSON to Qwen3-4B without re-running VLM"
                    >
                      <RefreshCw size={12} className={isCategorizing ? "animate-spin" : ""} />
                      <span>{isCategorizing ? "Running..." : "Re-run Accounting"}</span>
                    </button>
                  </div>

                  <div
                    style={{
                      overflowX: "auto",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-sm)",
                      background: "#ffffff",
                    }}
                  >
                    <table style={{ width: "100%", minWidth: "750px", borderCollapse: "collapse", fontSize: "12px" }}>
                      <thead>
                        <tr style={{ background: "#f9f9fb", borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", textAlign: "left" }}>
                          <th style={{ padding: "8px 8px", width: "30px" }}>#</th>
                          <th style={{ padding: "8px 8px", minWidth: "180px" }}>Item Description</th>
                          <th style={{ padding: "8px 8px", minWidth: "220px" }}>Suggested Account (COA)</th>
                          <th style={{ padding: "8px 8px", width: "90px" }}>Account Code</th>
                          <th style={{ padding: "8px 8px", width: "80px", textAlign: "center" }}>Confidence</th>
                          <th style={{ padding: "8px 8px", width: "90px", textAlign: "center" }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {accountingLines && accountingLines.length > 0 ? (
                          accountingLines.map((acc, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                              <td style={{ padding: "8px", color: "var(--text-tertiary)", textAlign: "center" }}>
                                {acc.line_index || idx + 1}
                              </td>
                              <td style={{ padding: "8px", fontWeight: "500" }}>
                                {acc.source_description || formData.line_items?.[idx]?.description || "-"}
                              </td>
                              <td style={{ padding: "8px" }}>
                                <input
                                  type="text"
                                  className="table-input"
                                  value={acc.final_account_name ?? acc.ai_account_name ?? ""}
                                  placeholder="Suggested Account"
                                  onChange={(e) => handleAccountingItemChange(idx, "final_account_name", e.target.value)}
                                />
                              </td>
                              <td style={{ padding: "8px" }}>
                                <code>{acc.final_account_id ?? acc.ai_account_id ?? "-"}</code>
                              </td>
                              <td style={{ padding: "8px", textAlign: "center" }}>
                                {acc.ai_confidence !== undefined && acc.ai_confidence !== null ? (
                                  <span
                                    className={`badge ${acc.ai_confidence >= 0.85
                                        ? "badge-success"
                                        : acc.ai_confidence >= 0.6
                                          ? "badge-uploaded"
                                          : "badge-danger"
                                      }`}
                                    style={{ fontSize: "11px" }}
                                  >
                                    {Math.round(acc.ai_confidence * 100)}%
                                  </span>
                                ) : (
                                  "-"
                                )}
                              </td>
                              <td style={{ padding: "8px", textAlign: "center" }}>
                                {acc.ai_needs_review ? (
                                  <span className="badge badge-danger" style={{ fontSize: "10px" }}>
                                    Review
                                  </span>
                                ) : (
                                  <span className="badge badge-success" style={{ fontSize: "10px" }}>
                                    Matched
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={6} style={{ padding: "20px", textAlign: "center", color: "var(--text-secondary)" }}>
                              No accounting classification generated yet. Click &quot;Re-run Accounting&quot; to classify with Qwen3-4B.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>

                {/* 9. TDS MODEL RESULT (ONLY IF RETURNED / AVAILABLE) */}
                {tdsResult && (
                  <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                      <Scale size={16} color="var(--accent)" />
                      <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                        9. TDS Analysis (Qwen3-4B)
                      </h3>
                      {tdsResult.applicable !== null && tdsResult.applicable !== undefined && (
                        <span
                          className={`badge ${tdsResult.applicable ? "badge-uploaded" : "badge-success"}`}
                          style={{ fontSize: "11px" }}
                        >
                          {tdsResult.applicable ? "TDS Applicable" : "TDS Not Applicable"}
                        </span>
                      )}
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                        gap: "12px",
                        background: "#fafafa",
                        padding: "14px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          TDS Section
                        </div>
                        <div style={{ fontWeight: "600", fontSize: "13px" }}>
                          {tdsResult.tds_section ? `Sec ${tdsResult.tds_section}` : "Not specified"}
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          TDS Rate
                        </div>
                        <div style={{ fontWeight: "600", fontSize: "13px" }}>
                          {tdsResult.tds_rate !== null && tdsResult.tds_rate !== undefined
                            ? `${tdsResult.tds_rate}%`
                            : "Not specified"}
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          TDS Base Amount
                        </div>
                        <div style={{ fontWeight: "600", fontSize: "13px" }}>
                          {tdsResult.tds_base_amount !== null && tdsResult.tds_base_amount !== undefined
                            ? `₹${tdsResult.tds_base_amount.toLocaleString()}`
                            : "-"}
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          Calculated TDS
                        </div>
                        <div style={{ fontWeight: "700", fontSize: "13px", color: "var(--accent)" }}>
                          {tdsResult.calculated_tds_amount !== null && tdsResult.calculated_tds_amount !== undefined
                            ? `₹${tdsResult.calculated_tds_amount.toLocaleString()}`
                            : "-"}
                        </div>
                      </div>

                      {tdsResult.reason && (
                        <div style={{ gridColumn: "1 / -1", marginTop: "4px" }}>
                          <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "2px" }}>
                            Model Reasoning
                          </div>
                          <div style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                            {tdsResult.reason}
                          </div>
                        </div>
                      )}
                    </div>
                  </section>
                )}

                {/* 10. ADDITIONAL EXTRACTED INFORMATION (ZERO DATA LOSS) */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                    <Layers size={16} color="var(--text-secondary)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      10. Additional Extracted Information
                    </h3>
                  </div>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "10px" }}>
                    Preserves non-standard or unmapped fields extracted by AI pipeline (Zero Data Loss).
                  </p>

                  <textarea
                    className="form-input"
                    rows={4}
                    style={{ fontFamily: "monospace", fontSize: "12px" }}
                    value={additionalFieldsText}
                    placeholder="{}"
                    onChange={(e) => setAdditionalFieldsText(e.target.value)}
                  />
                </section>

                {/* 11. SAVE CHANGES (WORKING BUTTON) */}
                <section
                  style={{
                    borderTop: "1px solid var(--border-subtle)",
                    paddingTop: "20px",
                    paddingBottom: "10px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    {saveSuccess && (
                      <span style={{ color: "var(--success)", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <CheckCircle2 size={16} /> Changes saved to database!
                      </span>
                    )}
                    {error && (
                      <span style={{ color: "var(--danger)", fontSize: "13px" }}>
                        {error}
                      </span>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={handleSaveChanges}
                    disabled={isSaving}
                    className="btn btn-primary"
                    style={{ padding: "10px 24px", fontSize: "14px" }}
                  >
                    <Save size={15} />
                    <span>{isSaving ? "Saving..." : "Save Changes"}</span>
                  </button>
                </section>
              </div>
            </div>
          </div>

          {/* ==================================================== */}
          {/* BOTTOM: PROCESSING WORKFLOW (3 EQUAL COLUMNS) */}
          {/* ==================================================== */}
          <div style={{ marginTop: "40px" }}>
            <div style={{ marginBottom: "16px" }}>
              <h2 style={{ fontSize: "18px", fontWeight: "700", letterSpacing: "-0.02em" }}>
                Processing Workflow
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                End-to-end invoice lifecycle from ingestion to Zoho export.
              </p>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "20px",
              }}
            >
              {/* 1. INCOMING INVOICES */}
              <div className="card" style={{ padding: "20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", paddingBottom: "12px", borderBottom: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    Incoming Invoices
                  </div>
                  <span className="badge badge-uploaded">{incomingInvoices.length}</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "300px", overflowY: "auto" }}>
                  {incomingInvoices.length > 0 ? (
                    incomingInvoices.map((item) => (
                      <div
                        key={item.id}
                        onClick={() => router.push(`/finance/invoices/${item.id}/processing`)}
                        style={{
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          background: item.id === invoiceId ? "#f0f7ff" : "var(--bg-main)",
                          border: item.id === invoiceId ? "1px solid var(--accent)" : "1px solid var(--border-subtle)",
                          cursor: "pointer",
                        }}
                      >
                        <div style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-primary)", marginBottom: "4px" }}>
                          {item.file_name}
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: "var(--text-secondary)" }}>
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <Clock size={11} /> {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </span>
                          <span className="badge badge-uploaded" style={{ fontSize: "10px" }}>
                            {item.status}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--text-tertiary)", fontSize: "13px" }}>
                      No pending incoming invoices.
                    </div>
                  )}
                </div>
              </div>

              {/* 2. EXTRACTED INVOICES */}
              <div className="card" style={{ padding: "20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", paddingBottom: "12px", borderBottom: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    Extracted Invoices
                  </div>
                  <span className="badge badge-success">{extractedInvoices.length}</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "300px", overflowY: "auto" }}>
                  {extractedInvoices.length > 0 ? (
                    extractedInvoices.map((item) => (
                      <div
                        key={item.id}
                        onClick={() => router.push(`/finance/invoices/${item.id}`)}
                        style={{
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          background: item.id === invoiceId ? "#f0fdf4" : "var(--bg-main)",
                          border: item.id === invoiceId ? "1px solid var(--success)" : "1px solid var(--border-subtle)",
                          cursor: "pointer",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                          <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-primary)" }}>
                            {item.invoice_number ? `INV #${item.invoice_number}` : item.file_name}
                          </span>
                          {item.total_amount && (
                            <span style={{ fontSize: "12px", fontWeight: "600" }}>
                              ₹{item.total_amount.toLocaleString()}
                            </span>
                          )}
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: "var(--text-secondary)" }}>
                          <span>{item.vendor_name || item.file_name}</span>
                          <span className="badge badge-success" style={{ fontSize: "10px" }}>
                            COMPLETED
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--text-tertiary)", fontSize: "13px" }}>
                      No extracted invoices yet.
                    </div>
                  )}
                </div>
              </div>

              {/* 3. EXPORTED TO ZOHO */}
              <div className="card" style={{ padding: "20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", paddingBottom: "12px", borderBottom: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    Exported to Zoho
                  </div>
                  <span className="badge badge-uploaded">0</span>
                </div>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "40px 16px",
                    textAlign: "center",
                    color: "var(--text-secondary)",
                  }}
                >
                  <Send size={28} color="var(--text-tertiary)" style={{ marginBottom: "10px", opacity: 0.6 }} />
                  <div style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-secondary)" }}>
                    No invoices exported yet.
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
                    Zoho Books synchronization activates in later Finance stages.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}

      <style jsx global>{`
        .form-label {
          display: block;
          font-size: 11px;
          font-weight: 600;
          color: var(--text-secondary);
          margin-bottom: 4px;
          text-transform: capitalize;
        }

        .form-input {
          width: 100%;
          padding: 8px 10px;
          font-size: 13px;
          background: #fdfdfd;
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-sm);
          color: var(--text-primary);
          outline: none;
          transition: border-color var(--transition-fast);
        }

        .form-input:focus {
          border-color: var(--accent);
          background: #ffffff;
          box-shadow: 0 0 0 1px var(--accent);
        }

        .table-input {
          width: 100%;
          padding: 4px 6px;
          font-size: 12px;
          background: transparent;
          border: 1px solid transparent;
          border-radius: 3px;
          color: var(--text-primary);
          outline: none;
        }

        .table-input:hover {
          border-color: var(--border-subtle);
          background: #ffffff;
        }

        .table-input:focus {
          border-color: var(--accent);
          background: #ffffff;
          box-shadow: 0 0 0 1px var(--accent);
        }

        @media (max-width: 1024px) {
          div[style*="gridTemplateColumns: minmax(420px"] {
            grid-template-columns: 1fr !important;
            height: auto !important;
          }
          div[style*="gridTemplateColumns: repeat(3, 1fr)"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
