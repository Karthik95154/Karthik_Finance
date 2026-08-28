"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getInvoice,
  getInvoiceFileUrl,
  updateInvoiceExtraction,
  triggerAccountingCategorization,
  listInvoices,
  getJournalPreview,
  approveInvoice,
  rejectInvoice,
  exportInvoiceToZoho,
  Invoice,
  InvoiceListItem,
  ExtractedInvoiceData,
  LineItem,
  BankDetails,
  RawVlmOutput,
  AccountingOutput,
  AccountingLineItem,
  TdsResult,
  GstResult,
  ItcResult,
  FinancialValidationResult,
  JournalEntry,
  JournalPreviewResponse,
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
  ShieldCheck,
  Landmark,
  Calculator,
} from "lucide-react";

// Helper to parse clean numeric values including currency strings like "Rupees 35,36,917.24" or "Rs. 248,417.88"
function parseCleanNumeric(val: any): number | null {
  if (val === null || val === undefined || val === "") return null;
  if (typeof val === "number") return isNaN(val) ? null : val;
  if (typeof val === "string") {
    let clean = val.trim().replace(/,/g, "");
    clean = clean.replace(/^(?:Rupees|Rupee|Rs\.?|INR|₹)\s*/i, "");
    clean = clean.replace(/\s*(?:\/-\s*|Only\s*)$/i, "");
    clean = clean.trim();
    const negative = clean.startsWith("(") && clean.endsWith(")");
    clean = clean.replace(/[()]/g, "").trim();
    const num = parseFloat(clean);
    if (!isNaN(num)) {
      return negative ? -num : num;
    }
  }
  return null;
}

// Helper to extract or derive invoice-level CGST/SGST/IGST amounts from Qwen3-VL extraction
function extractOrDeriveTax(
  extracted: ExtractedInvoiceData,
  taxType: "cgst" | "sgst" | "igst"
): number | null {
  if (!extracted || typeof extracted !== "object") return null;

  // Support both direct object and nested .data object
  const dataObj =
    (extracted as any).data && typeof (extracted as any).data === "object"
      ? (extracted as any).data
      : extracted;

  const exactKeys = {
    cgst: ["cgst", "cgst_amount", "cgst_total", "total_cgst", "cgst_tax", "c_gst"],
    sgst: ["sgst", "sgst_amount", "sgst_total", "total_sgst", "sgst_tax", "s_gst", "utgst", "utgst_amount"],
    igst: ["igst", "igst_amount", "igst_total", "total_igst", "igst_tax", "i_gst"],
  }[taxType];

  // 1. Direct explicit top-level values
  for (const src of [extracted, dataObj]) {
    for (const k of exactKeys) {
      if (k in src && (src as any)[k] !== null && (src as any)[k] !== undefined && (src as any)[k] !== "") {
        const val = parseCleanNumeric((src as any)[k]);
        if (val !== null) return val;
      }
      const upperK = k.toUpperCase();
      if (upperK in src && (src as any)[upperK] !== null && (src as any)[upperK] !== undefined && (src as any)[upperK] !== "") {
        const val = parseCleanNumeric((src as any)[upperK]);
        if (val !== null) return val;
      }
    }
  }

  // 2. Search inside additional_fields (and nested tax_details)
  for (const src of [extracted, dataObj]) {
    const af = src.additional_fields;
    if (af && typeof af === "object") {
      for (const [k, v] of Object.entries(af)) {
        if (v === null || v === undefined || v === "") continue;
        const cleanKey = k.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
        if (
          taxType === "cgst" &&
          ["cgst", "cgstamount", "cgsttotal", "cgsttax", "centralgst", "centralgstamount", "cgstamt"].includes(cleanKey)
        ) {
          const val = parseCleanNumeric(v);
          if (val !== null) return val;
        } else if (
          taxType === "sgst" &&
          ["sgst", "sgstamount", "sgsttotal", "sgsttax", "stategst", "utgst", "utgstamount", "sgstamt"].includes(cleanKey)
        ) {
          const val = parseCleanNumeric(v);
          if (val !== null) return val;
        } else if (
          taxType === "igst" &&
          ["igst", "igstamount", "igsttotal", "igsttax", "integratedgst", "igstamt"].includes(cleanKey)
        ) {
          const val = parseCleanNumeric(v);
          if (val !== null) return val;
        }
      }

      const td = (af as any).tax_details;
      if (td && typeof td === "object") {
        const sections = ["output_tax", "tax_payable", "input_tax_credit", "tax_breakdown", ""];
        for (const section of sections) {
          const target = section ? td[section] : td;
          if (target && typeof target === "object") {
            for (const k of exactKeys) {
              if (k in target && target[k] !== null && target[k] !== undefined && target[k] !== "") {
                const val = parseCleanNumeric(target[k]);
                if (val !== null) return val;
              }
              const upperK = k.toUpperCase();
              if (upperK in target && target[upperK] !== null && target[upperK] !== undefined && target[upperK] !== "") {
                const val = parseCleanNumeric(target[upperK]);
                if (val !== null) return val;
              }
            }
          }
        }
      }
    }
  }

  // 3. Line items - explicit tax amount or rate * taxable
  const line_items = dataObj.line_items || extracted.line_items;
  if (Array.isArray(line_items) && line_items.length > 0) {
    const lineVals: number[] = [];
    for (const item of line_items) {
      if (!item || typeof item !== "object") continue;
      let foundVal: number | null = null;
      for (const k of exactKeys) {
        if (k in item && (item as any)[k] !== null && (item as any)[k] !== undefined && (item as any)[k] !== "") {
          const val = parseCleanNumeric((item as any)[k]);
          if (val !== null) {
            foundVal = val;
            break;
          }
        }
        const upperK = k.toUpperCase();
        if (upperK in item && (item as any)[upperK] !== null && (item as any)[upperK] !== undefined && (item as any)[upperK] !== "") {
          const val = parseCleanNumeric((item as any)[upperK]);
          if (val !== null) {
            foundVal = val;
            break;
          }
        }
      }

      // If explicit line tax amount is omitted, check rate * taxable
      if (foundVal === null) {
        const rateKey = taxType + "_rate";
        const rateVal = parseCleanNumeric((item as any)[rateKey] || (item as any)[rateKey.toUpperCase()]);
        const taxableVal = parseCleanNumeric(
          item.taxable_amount ??
          (item as any).taxable ??
          (item as any).pretax_amount ??
          (typeof item.unit_price === "number" && typeof item.quantity === "number" ? item.unit_price * item.quantity : null)
        );
        if (rateVal !== null && rateVal > 0 && taxableVal !== null && taxableVal > 0) {
          foundVal = Math.round(((taxableVal * rateVal) / 100) * 100) / 100;
        }
      }

      if (foundVal !== null) {
        lineVals.push(foundVal);
      }
    }
    if (lineVals.length > 0) {
      return Math.round(lineVals.reduce((a, b) => a + b, 0) * 100) / 100;
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
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [journalPreview, setJournalPreview] = useState<JournalPreviewResponse | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [journalPreview, setJournalPreview] = useState<JournalPreviewResponse | null>(null);

  // Editable form state
  const [formData, setFormData] = useState<ExtractedInvoiceData>({});
  const [accountingData, setAccountingData] = useState<AccountingOutput>({});
  const [gstResult, setGstResult] = useState<GstResult | null>(null);
  const [itcResult, setItcResult] = useState<ItcResult | null>(null);
  const [financialValidationResult, setFinancialValidationResult] = useState<FinancialValidationResult | null>(null);
  const [journalEntry, setJournalEntry] = useState<JournalEntry | null>(null);
  const [additionalFieldsText, setAdditionalFieldsText] = useState<string>("");

  useEffect(() => {
    if (!invoiceId) return;

    async function loadData() {
      try {
        setLoading(true);
        const [invData, listData, jPreview] = await Promise.all([
          getInvoice(invoiceId),
          listInvoices().catch(() => []),
          getJournalPreview(invoiceId).catch(() => null),
        ]);

        setInvoice(invData);
        setWorkflowInvoices(listData);
        getJournalPreview(invoiceId).then(setJournalPreview).catch(() => null);

        // If still in initial stages, route to processing page
        if (
          invData.status === "PENDING" ||
          invData.status === "PROCESSING_VLM" ||
          invData.status === "PROCESSING_ACCOUNTING"
        ) {
          router.push(`/finance/invoices/${invoiceId}/processing`);
          return;
        }

        // Initialize form state from current_vlm_output (edited) merged over raw_vlm_output (base)
        const rawData: ExtractedInvoiceData =
          invData.raw_vlm_output && (invData.raw_vlm_output as any).data
            ? (invData.raw_vlm_output as any).data
            : (invData.raw_vlm_output as ExtractedInvoiceData) || {};

        const currData: ExtractedInvoiceData =
          invData.current_vlm_output && (invData.current_vlm_output as any).data
            ? (invData.current_vlm_output as any).data
            : (invData.current_vlm_output as ExtractedInvoiceData) || {};

        // Merge raw extraction with user-edited fields, ensuring line_items and totals are never wiped
        const extracted: ExtractedInvoiceData = {
          ...rawData,
          ...currData,
        };

        if (!extracted.line_items || extracted.line_items.length === 0) {
          if (Array.isArray(rawData.line_items) && rawData.line_items.length > 0) {
            extracted.line_items = [...rawData.line_items];
          } else {
            extracted.line_items = [];
          }
        }
        if (extracted.subtotal === undefined || extracted.subtotal === null) {
          extracted.subtotal = rawData.subtotal ?? null;
        }
        if (extracted.tax_total === undefined || extracted.tax_total === null) {
          extracted.tax_total = rawData.tax_total ?? null;
        }
        if (extracted.total_amount === undefined || extracted.total_amount === null) {
          extracted.total_amount = rawData.total_amount ?? null;
        }

        // Extract or derive CGST, SGST, IGST:
        // Priority: explicit edits in currData > derived from currData > explicit in rawData > derived from rawData
        const extractedCgst = extractOrDeriveTax(currData, "cgst") ?? extractOrDeriveTax(rawData, "cgst");
        extracted.cgst = extractedCgst;
        extracted.cgst_amount = extractedCgst;

        const extractedSgst = extractOrDeriveTax(currData, "sgst") ?? extractOrDeriveTax(rawData, "sgst");
        extracted.sgst = extractedSgst;
        extracted.sgst_amount = extractedSgst;

        const extractedIgst = extractOrDeriveTax(currData, "igst") ?? extractOrDeriveTax(rawData, "igst");
        extracted.igst = extractedIgst;
        extracted.igst_amount = extractedIgst;

        if (!extracted.bank_details) extracted.bank_details = rawData.bank_details || {};

        setFormData(extracted);
        setAdditionalFieldsText(
          extracted.additional_fields
            ? JSON.stringify(extracted.additional_fields, null, 2)
            : rawData.additional_fields
            ? JSON.stringify(rawData.additional_fields, null, 2)
            : ""
        );

        // Initialize accounting data from current_accounting_output or accounting_output
        const accOutput =
          invData.current_accounting_output || invData.accounting_output || {};
        setAccountingData(accOutput);
        setGstResult(invData.gst_result || null);
        setItcResult(invData.itc_result || null);
        setFinancialValidationResult(invData.financial_validation_result || null);
        setJournalEntry(invData.journal_entry || null);
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
      if (updated.gst_result) setGstResult(updated.gst_result);
      if (updated.itc_result) setItcResult(updated.itc_result);
      if (updated.financial_validation_result) setFinancialValidationResult(updated.financial_validation_result);
      if (updated.journal_entry) setJournalEntry(updated.journal_entry);
      setSaveSuccess(true);

      // Refresh journal preview with saved changes
      getJournalPreview(invoiceId).then(setJournalPreview).catch(() => null);

      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to save changes.");
    } finally {
      setIsSaving(false);
    }
  };

  // Accept AI suggestions into approved fields for all lines
  const handleAcceptAllAccounts = () => {
    const updated = (accountingData.accounting || []).map((acc, idx) => {
      const id = acc.final_account_id || acc.ai_account_id || `ACC_${idx + 1}`;
      const name = acc.final_account_name || acc.ai_account_name || "General Expenses";
      return {
        ...acc,
        approved_account_id: id,
        approved_account_name: name,
        final_account_id: id,
        final_account_name: name,
      };
    });
    setAccountingData({ ...accountingData, accounting: updated });
    setActionNotice("Accepted all suggested Chart of Accounts.");
    setTimeout(() => setActionNotice(null), 3000);
  };

  // Accept a single AI suggestion
  const handleAcceptAccount = (index: number) => {
    const updated = [...(accountingData.accounting || [])];
    if (updated[index]) {
      const id = updated[index].final_account_id || updated[index].ai_account_id || `ACC_${index + 1}`;
      const name = updated[index].final_account_name || updated[index].ai_account_name || "General Expenses";
      updated[index] = {
        ...updated[index],
        approved_account_id: id,
        approved_account_name: name,
        final_account_id: id,
        final_account_name: name,
      };
      setAccountingData({ ...accountingData, accounting: updated });
    }
  };

  // Real Approval Action Handler
  const handleApprove = async () => {
    try {
      setIsApproving(true);
      setError(null);

      // 1. Ensure all line items have Finance-approved Chart of Accounts populated
      const currentLines = [...(accountingData.accounting || [])];
      if (!currentLines || currentLines.length === 0) {
        throw new Error("No accounting classifications available. Please click 'Re-run Accounting' first.");
      }

      const updatedLines = currentLines.map((item, idx) => {
        const approvedId =
          item.approved_account_id ||
          item.final_account_id ||
          item.ai_account_id ||
          `ACC_${idx + 1}`;
        const approvedName =
          item.approved_account_name ||
          item.final_account_name ||
          item.ai_account_name ||
          "General Expenses";
        return {
          ...item,
          approved_account_id: approvedId,
          approved_account_name: approvedName,
          final_account_id: approvedId,
          final_account_name: approvedName,
        };
      });

      const updatedAccounting = {
        ...accountingData,
        accounting: updatedLines,
      };

      // 2. Persist the approved accounts and form data to backend
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

      await updateInvoiceExtraction(
        invoiceId,
        updatedVlmPayload,
        updatedAccounting
      );
      setAccountingData(updatedAccounting);

      // 3. Execute authoritative Finance Approval and generate General Ledger Journal
      await approveInvoice(invoiceId);
      setActionNotice("Invoice approved and balanced double-entry journal created!");
      setTimeout(() => setActionNotice(null), 4000);
      
      const [updatedInv, updatedJournal] = await Promise.all([
        getInvoice(invoiceId),
        getJournalPreview(invoiceId).catch(() => null),
      ]);
      setInvoice(updatedInv);
      if (updatedJournal) setJournalPreview(updatedJournal);
    } catch (err: any) {
      setError(err.message || "Failed to approve invoice.");
    } finally {
      setIsApproving(false);
    }
  };

  // Real Rejection Action Handler
  const handleRejectConfirm = async () => {
    if (!rejectReason.trim()) {
      setError("Please enter a rejection reason.");
      return;
    }
    try {
      setIsRejecting(true);
      setError(null);
      await rejectInvoice(invoiceId, rejectReason);
      setRejectModalOpen(false);
      setRejectReason("");
      setActionNotice("Invoice rejected.");
      setTimeout(() => setActionNotice(null), 4000);
      
      const updatedInv = await getInvoice(invoiceId);
      setInvoice(updatedInv);
    } catch (err: any) {
      setError(err.message || "Failed to reject invoice.");
    } finally {
      setIsRejecting(false);
    }
  };

  // Real Zoho Export Action Handler
  const handleExport = async () => {
    try {
      setIsExporting(true);
      setError(null);
      const res = await exportInvoiceToZoho(invoiceId);
      setActionNotice(`Successfully exported to Zoho Books! Bill #${res.zoho_bill_number || res.zoho_bill_id}`);
      
      const updatedInv = await getInvoice(invoiceId);
      setInvoice(updatedInv);
    } catch (err: any) {
      setError(err.message || "Failed to export invoice to Zoho Books.");
    } finally {
      setIsExporting(false);
    }
  };

  // Categorized invoice workflow lists
  const incomingInvoices = workflowInvoices.filter(
    (inv) =>
      inv.status === "PENDING" ||
      inv.status === "PROCESSING_VLM" ||
      inv.status === "PROCESSING_ACCOUNTING"
  );
  const extractedInvoices = workflowInvoices.filter(
    (inv) => inv.status === "COMPLETED" && inv.export_status !== "EXPORTED"
  );
  const exportedInvoices = workflowInvoices.filter(
    (inv) => inv.export_status === "EXPORTED" || Boolean(inv.zoho_bill_id)
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
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <button
            onClick={() => router.push("/finance/invoices")}
            className="btn btn-secondary"
            style={{ padding: "6px 12px", fontSize: "13px" }}
            title="Return to Invoice Registry"
          >
            <ArrowLeft size={14} />
            <span>Invoices</span>
          </button>
          <button
            onClick={() => router.push("/dashboard")}
            className="btn btn-secondary"
            style={{ padding: "6px 10px", fontSize: "12px" }}
            title="Return to Dashboard"
          >
            <span>Dashboard</span>
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

        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          {invoice?.accounting_confidence !== null && invoice?.accounting_confidence !== undefined && (
            <span className="badge badge-uploaded" style={{ fontSize: "12px", color: "var(--accent)" }}>
              COA: {Math.round(invoice.accounting_confidence * 100)}%
            </span>
          )}

          {invoice?.approval_status && (
            <span
              className={`badge ${
                invoice.approval_status === "APPROVED"
                  ? "badge-success"
                  : invoice.approval_status === "REJECTED"
                  ? "badge-danger"
                  : "badge-uploaded"
              }`}
              style={{ fontSize: "12px" }}
            >
              {invoice.approval_status === "APPROVED"
                ? "Approved ✓"
                : invoice.approval_status === "REJECTED"
                ? "Rejected ✗"
                : "Pending Review"}
            </span>
          )}

          {invoice?.export_status === "EXPORTED" ? (
            <span className="badge badge-success" style={{ fontSize: "12px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
              <ShieldCheck size={13} />
              Zoho Bill: {invoice.zoho_bill_number ? `#${invoice.zoho_bill_number}` : invoice.zoho_bill_id || "Exported ✓"}
            </span>
          ) : (
            <span className="badge badge-uploaded" style={{ fontSize: "12px" }}>
              {invoice?.export_status || "NOT_EXPORTED"}
            </span>
          )}

          {/* Action Buttons: Reject, Approve, Export to Zoho */}
          {invoice?.approval_status !== "APPROVED" && (
            <button
              onClick={() => setRejectModalOpen(true)}
              className="btn btn-secondary"
              style={{
                padding: "6px 12px",
                fontSize: "12px",
                color: "var(--danger)",
                borderColor: "rgba(255, 69, 58, 0.3)",
              }}
            >
              <X size={13} />
              <span>Reject</span>
            </button>
          )}

          <button
            onClick={handleApprove}
            disabled={isApproving || invoice?.approval_status === "APPROVED"}
            className="btn btn-primary"
            style={{
              padding: "6px 14px",
              fontSize: "12px",
              background:
                invoice?.approval_status === "APPROVED"
                  ? "#34c759"
                  : "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
            }}
          >
            <Check size={13} />
            <span>
              {isApproving
                ? "Balancing & Approving..."
                : invoice?.approval_status === "APPROVED"
                ? "Approved ✓"
                : "Approve"}
            </span>
          </button>

          <button
            onClick={handleExport}
            disabled={
              isExporting ||
              invoice?.approval_status !== "APPROVED" ||
              invoice?.export_status === "EXPORTED"
            }
            className="btn btn-primary"
            style={{
              padding: "6px 14px",
              fontSize: "12px",
              background:
                invoice?.export_status === "EXPORTED"
                  ? "#34c759"
                  : invoice?.approval_status === "APPROVED"
                  ? "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)"
                  : "var(--border-subtle)",
              color: invoice?.approval_status === "APPROVED" ? "#ffffff" : "var(--text-tertiary)",
              cursor:
                invoice?.approval_status === "APPROVED" && invoice?.export_status !== "EXPORTED"
                  ? "pointer"
                  : "not-allowed",
            }}
            title={
              invoice?.approval_status !== "APPROVED"
                ? "Must approve invoice with authoritative Chart of Accounts before exporting to Zoho Books"
                : "Export bill to Zoho Books"
            }
          >
            <Send size={13} />
            <span>
              {isExporting
                ? "Syncing to Zoho..."
                : invoice?.export_status === "EXPORTED"
                ? "Exported to Zoho ✓"
                : "Export to Zoho"}
            </span>
          </button>
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
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "2px" }}>
                    <span style={{ fontSize: "11px", fontWeight: "700", letterSpacing: "0.06em", color: "var(--text-secondary)", textTransform: "uppercase" }}>
                      AI Extraction Review
                    </span>
                    {invoice?.approval_status === "APPROVED" && (
                      <span className="badge badge-success" style={{ fontSize: "10px", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                        <Check size={10} /> Approved
                      </span>
                    )}
                    {invoice?.approval_status === "REJECTED" && (
                      <span className="badge badge-danger" style={{ fontSize: "10px", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                        <X size={10} /> Rejected
                      </span>
                    )}
                    {invoice?.export_status === "EXPORTED" && (
                      <span className="badge badge-uploaded" style={{ fontSize: "10px", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                        <Send size={10} /> Zoho Synced
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-primary)" }}>
                    Final Invoice & Accounting Workspace
                  </div>
                </div>

                {/* Top Right Action Buttons: Reject, Approve, Export */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  {invoice?.approval_status !== "APPROVED" && (
                    <button
                      type="button"
                      onClick={() => setRejectModalOpen(true)}
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
                  )}
                  <button
                    type="button"
                    onClick={handleApprove}
                    disabled={isApproving || invoice?.approval_status === "APPROVED"}
                    className="btn btn-secondary"
                    style={{
                      padding: "6px 12px",
                      fontSize: "12px",
                      color: invoice?.approval_status === "APPROVED" ? "#34c759" : "var(--success)",
                      borderColor: "var(--border-subtle)",
                      background: invoice?.approval_status === "APPROVED" ? "#f0fdf4" : undefined,
                    }}
                  >
                    <Check size={14} />
                    <span>{isApproving ? "Approving..." : invoice?.approval_status === "APPROVED" ? "Approved ✓" : "Approve"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleExport}
                    disabled={isExporting || invoice?.approval_status !== "APPROVED" || invoice?.export_status === "EXPORTED"}
                    className="btn btn-secondary"
                    style={{
                      padding: "6px 14px",
                      fontSize: "12px",
                      color: invoice?.export_status === "EXPORTED" ? "#34c759" : "var(--accent)",
                      borderColor: "var(--border-subtle)",
                    }}
                    title={invoice?.approval_status !== "APPROVED" ? "Approve the invoice first to export to Zoho Books" : "Export approved bill to Zoho Books"}
                  >
                    <Send size={14} />
                    <span>{isExporting ? "Exporting..." : invoice?.export_status === "EXPORTED" ? "Exported ✓" : "Export"}</span>
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
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <BookOpen size={16} color="var(--accent)" />
                      <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                        8. Accounting Classification &amp; COA Review
                      </h3>
                      {accountingLines.length > 0 && (
                        <span className="badge badge-success" style={{ fontSize: "11px" }}>
                          {accountingLines.length} classified
                        </span>
                      )}
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      {accountingLines.length > 0 && (
                        <button
                          type="button"
                          onClick={handleAcceptAllAccounts}
                          className="btn btn-secondary"
                          style={{
                            padding: "4px 10px",
                            fontSize: "12px",
                            color: "var(--accent)",
                            borderColor: "var(--accent)",
                          }}
                          title="Accept all AI suggestions as approved accounts"
                        >
                          <Check size={12} />
                          <span>Accept All Accounts</span>
                        </button>
                      )}

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
                  </div>

                  <div
                    style={{
                      overflowX: "auto",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-sm)",
                      background: "#ffffff",
                    }}
                  >
                    <table style={{ width: "100%", minWidth: "800px", borderCollapse: "collapse", fontSize: "12px" }}>
                      <thead>
                        <tr style={{ background: "#f9f9fb", borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", textAlign: "left" }}>
                          <th style={{ padding: "8px 8px", width: "30px" }}>#</th>
                          <th style={{ padding: "8px 8px", minWidth: "160px" }}>Item Description</th>
                          <th style={{ padding: "8px 8px", minWidth: "200px" }}>Suggested Account (COA)</th>
                          <th style={{ padding: "8px 8px", width: "90px" }}>Account Code</th>
                          <th style={{ padding: "8px 8px", width: "80px", textAlign: "center" }}>Confidence</th>
                          <th style={{ padding: "8px 8px", width: "80px", textAlign: "center" }}>Action</th>
                          <th style={{ padding: "8px 8px", width: "80px", textAlign: "center" }}>Status</th>
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
                                  value={acc.approved_account_name || acc.final_account_name || acc.ai_account_name || ""}
                                  placeholder="Approved Account"
                                  onChange={(e) => {
                                    handleAccountingItemChange(idx, "final_account_name", e.target.value);
                                    handleAccountingItemChange(idx, "approved_account_name", e.target.value);
                                  }}
                                />
                              </td>
                              <td style={{ padding: "8px" }}>
                                <code>{acc.approved_account_id || acc.final_account_id || acc.ai_account_id || "-"}</code>
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
                                {acc.approved_account_id ? (
                                  <span style={{ fontSize: "11px", color: "#34c759", fontWeight: "600" }}>
                                    Approved ✓
                                  </span>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => handleAcceptAccount(idx)}
                                    className="btn btn-secondary"
                                    style={{ padding: "2px 8px", fontSize: "11px" }}
                                  >
                                    Accept
                                  </button>
                                )}
                              </td>
                              <td style={{ padding: "8px", textAlign: "center" }}>
                                {acc.ai_needs_review && !acc.approved_account_id ? (
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
                            <td colSpan={7} style={{ padding: "20px", textAlign: "center", color: "var(--text-secondary)" }}>
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

                {/* 9. GST VALIDATION (STAGE 4 DETERMINISTIC ENGINE) */}
                {gstResult && (
                  <section
                    style={{
                      borderTop: "1px solid var(--border-subtle)",
                      paddingTop: "18px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "12px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <ShieldCheck size={16} color="var(--accent)" />
                        <h3
                          style={{
                            fontSize: "14px",
                            fontWeight: "700",
                            letterSpacing: "0.02em",
                            textTransform: "uppercase",
                          }}
                        >
                          9. GST Structure Validation
                        </h3>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span
                          className={`badge ${
                            gstResult.supply_type === "INTRA_STATE"
                              ? "badge-success"
                              : gstResult.supply_type === "INTER_STATE"
                              ? "badge-uploaded"
                              : "badge-warning"
                          }`}
                          style={{ fontSize: "11px", fontWeight: "600" }}
                        >
                          {gstResult.supply_type === "INTRA_STATE"
                            ? "Intra-State (CGST+SGST)"
                            : gstResult.supply_type === "INTER_STATE"
                            ? "Inter-State (IGST)"
                            : "Review Required"}
                        </span>
                        <span
                          className={`badge ${
                            gstResult.validation_status === "PASSED"
                              ? "badge-success"
                              : gstResult.validation_status === "GST_MISMATCH"
                              ? "badge-warning"
                              : "badge-uploaded"
                          }`}
                          style={{ fontSize: "11px", fontWeight: "700" }}
                        >
                          {gstResult.validation_status || "PENDING"}
                        </span>
                      </div>
                    </div>

                    {/* GST Identification Grid */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(4, 1fr)",
                        gap: "12px",
                        background: "var(--bg-main)",
                        padding: "12px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        marginBottom: "14px",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          Supplier GSTIN & State
                        </div>
                        <div style={{ fontWeight: "600", fontSize: "12px", fontFamily: "monospace" }}>
                          {formData.vendor_gstin || "-"}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                          {gstResult.supplier_state_code
                            ? `${gstResult.supplier_state_code} - ${gstResult.supplier_state_name}`
                            : "Unresolved"}
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          Buyer GSTIN & State
                        </div>
                        <div style={{ fontWeight: "600", fontSize: "12px", fontFamily: "monospace" }}>
                          {formData.customer_gstin || "-"}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                          {gstResult.buyer_state_code
                            ? `${gstResult.buyer_state_code} - ${gstResult.buyer_state_name}`
                            : "Unresolved"}
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          Place of Supply (POS)
                        </div>
                        <div style={{ fontWeight: "600", fontSize: "12px" }}>
                          {gstResult.place_of_supply_state_name
                            ? `${gstResult.place_of_supply_state_code} - ${gstResult.place_of_supply_state_name}`
                            : "Unresolved"}
                        </div>
                        <div style={{ fontSize: "10px", color: "var(--accent)", marginTop: "2px" }}>
                          Source: {gstResult.place_of_supply_source === "explicit_invoice" ? "Explicit Invoice" : gstResult.place_of_supply_source === "buyer_gstin_fallback" ? "Buyer GSTIN Fallback" : "Unresolved"}
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          Reverse Charge (RCM)
                        </div>
                        <div style={{ fontWeight: "600", fontSize: "12px" }}>
                          {gstResult.is_reverse_charge ? "Yes (RCM Applicable)" : "No"}
                        </div>
                      </div>
                    </div>

                    {/* Extracted vs Calculated Tax Comparison Table */}
                    <div style={{ overflowX: "auto", marginBottom: "12px" }}>
                      <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse", textAlign: "left" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", background: "var(--bg-main)" }}>
                            <th style={{ padding: "8px" }}>Tax Component</th>
                            <th style={{ padding: "8px", textAlign: "right" }}>Extracted (Source)</th>
                            <th style={{ padding: "8px", textAlign: "right" }}>Calculated (Engine)</th>
                            <th style={{ padding: "8px", textAlign: "center" }}>Validation</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                            <td style={{ padding: "8px", fontWeight: "600" }}>CGST (Central Tax)</td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                              {gstResult.extracted?.cgst_amount !== null && gstResult.extracted?.cgst_amount !== undefined
                                ? `₹${gstResult.extracted.cgst_amount.toLocaleString()}`
                                : "-"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                              {gstResult.calculated?.cgst_amount !== null && gstResult.calculated?.cgst_amount !== undefined
                                ? `₹${gstResult.calculated.cgst_amount.toLocaleString()}`
                                : "₹0.00"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "center" }}>
                              {gstResult.supply_type === "INTRA_STATE" ? (
                                <Check size={14} color="var(--success)" style={{ margin: "0 auto" }} />
                              ) : gstResult.extracted?.cgst_amount ? (
                                <X size={14} color="var(--danger)" style={{ margin: "0 auto" }} />
                              ) : (
                                <span style={{ color: "var(--text-tertiary)" }}>-</span>
                              )}
                            </td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                            <td style={{ padding: "8px", fontWeight: "600" }}>SGST / UTGST (State Tax)</td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                              {gstResult.extracted?.sgst_amount !== null && gstResult.extracted?.sgst_amount !== undefined
                                ? `₹${gstResult.extracted.sgst_amount.toLocaleString()}`
                                : "-"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                              {gstResult.calculated?.sgst_amount !== null && gstResult.calculated?.sgst_amount !== undefined
                                ? `₹${gstResult.calculated.sgst_amount.toLocaleString()}`
                                : "₹0.00"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "center" }}>
                              {gstResult.supply_type === "INTRA_STATE" ? (
                                <Check size={14} color="var(--success)" style={{ margin: "0 auto" }} />
                              ) : gstResult.extracted?.sgst_amount ? (
                                <X size={14} color="var(--danger)" style={{ margin: "0 auto" }} />
                              ) : (
                                <span style={{ color: "var(--text-tertiary)" }}>-</span>
                              )}
                            </td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                            <td style={{ padding: "8px", fontWeight: "600" }}>IGST (Integrated Tax)</td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                              {gstResult.extracted?.igst_amount !== null && gstResult.extracted?.igst_amount !== undefined
                                ? `₹${gstResult.extracted.igst_amount.toLocaleString()}`
                                : "-"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                              {gstResult.calculated?.igst_amount !== null && gstResult.calculated?.igst_amount !== undefined
                                ? `₹${gstResult.calculated.igst_amount.toLocaleString()}`
                                : "₹0.00"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "center" }}>
                              {gstResult.supply_type === "INTER_STATE" ? (
                                <Check size={14} color="var(--success)" style={{ margin: "0 auto" }} />
                              ) : gstResult.extracted?.igst_amount ? (
                                <X size={14} color="var(--danger)" style={{ margin: "0 auto" }} />
                              ) : (
                                <span style={{ color: "var(--text-tertiary)" }}>-</span>
                              )}
                            </td>
                          </tr>
                          <tr style={{ background: "var(--bg-main)", fontWeight: "700" }}>
                            <td style={{ padding: "8px" }}>Total GST</td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace", color: "var(--accent)" }}>
                              {gstResult.extracted?.tax_total !== null && gstResult.extracted?.tax_total !== undefined
                                ? `₹${gstResult.extracted.tax_total.toLocaleString()}`
                                : "-"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace", color: "var(--accent)" }}>
                              {gstResult.calculated?.gst_total !== null && gstResult.calculated?.gst_total !== undefined
                                ? `₹${gstResult.calculated.gst_total.toLocaleString()}`
                                : "₹0.00"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "center" }}>
                              {gstResult.validation_status === "PASSED" ? (
                                <span style={{ color: "var(--success)", fontSize: "11px" }}>MATCH</span>
                              ) : (
                                <span style={{ color: "var(--danger)", fontSize: "11px" }}>CHECK</span>
                              )}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* Errors & Warnings */}
                    {gstResult.errors && gstResult.errors.length > 0 && (
                      <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "var(--radius-sm)", padding: "10px 14px", marginBottom: "8px", fontSize: "12px", color: "#991b1b" }}>
                        {gstResult.errors.map((err, i) => (
                          <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: i < gstResult.errors!.length - 1 ? "4px" : "0" }}>
                            <AlertCircle size={14} /> <span>{err}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {gstResult.warnings && gstResult.warnings.length > 0 && (
                      <div style={{ background: "#fefce8", border: "1px solid #fef08a", borderRadius: "var(--radius-sm)", padding: "10px 14px", fontSize: "12px", color: "#854d0e" }}>
                        {gstResult.warnings.map((w, i) => (
                          <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: i < gstResult.warnings!.length - 1 ? "4px" : "0" }}>
                            <AlertCircle size={14} /> <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                )}

                {/* 10. INPUT TAX CREDIT (ITC) (STAGE 4 DETERMINISTIC ENGINE) */}
                {itcResult && (
                  <section
                    style={{
                      borderTop: "1px solid var(--border-subtle)",
                      paddingTop: "18px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "12px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Landmark size={16} color="var(--accent)" />
                        <h3
                          style={{
                            fontSize: "14px",
                            fontWeight: "700",
                            letterSpacing: "0.02em",
                            textTransform: "uppercase",
                          }}
                        >
                          10. Input Tax Credit (ITC) Eligibility
                        </h3>
                      </div>
                      <span
                        className={`badge ${
                          itcResult.status === "ELIGIBLE"
                            ? "badge-success"
                            : itcResult.status === "INELIGIBLE"
                            ? "badge-warning"
                            : "badge-uploaded"
                        }`}
                        style={{ fontSize: "11px", fontWeight: "700" }}
                      >
                        {itcResult.status}
                      </span>
                    </div>

                    {/* ITC Summary Cards */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(3, 1fr)",
                        gap: "12px",
                        marginBottom: "14px",
                      }}
                    >
                      <div
                        style={{
                          background: "var(--bg-main)",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border-subtle)",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          Total Tax Available
                        </div>
                        <div style={{ fontWeight: "700", fontSize: "15px" }}>
                          ₹{itcResult.total_tax_amount?.toLocaleString() || "0.00"}
                        </div>
                      </div>

                      <div
                        style={{
                          background: "#f0fdf4",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid #bbf7d0",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: "#166534", marginBottom: "3px" }}>
                          Eligible ITC (Claimable)
                        </div>
                        <div style={{ fontWeight: "700", fontSize: "15px", color: "#15803d" }}>
                          ₹{itcResult.eligible_amount?.toLocaleString() || "0.00"}
                        </div>
                      </div>

                      <div
                        style={{
                          background: itcResult.ineligible_amount > 0 ? "#fef2f2" : "var(--bg-main)",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: itcResult.ineligible_amount > 0 ? "1px solid #fecaca" : "1px solid var(--border-subtle)",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: itcResult.ineligible_amount > 0 ? "#991b1b" : "var(--text-secondary)", marginBottom: "3px" }}>
                          Blocked / Ineligible (Sec 17(5))
                        </div>
                        <div style={{ fontWeight: "700", fontSize: "15px", color: itcResult.ineligible_amount > 0 ? "#b91c1c" : "var(--text-primary)" }}>
                          ₹{itcResult.ineligible_amount?.toLocaleString() || "0.00"}
                        </div>
                      </div>
                    </div>

                    {/* Statutory Reason & Rule Reference */}
                    <div
                      style={{
                        background: "var(--bg-main)",
                        padding: "12px 14px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        fontSize: "12px",
                        marginBottom: "12px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                        <span style={{ fontWeight: "600", color: "var(--text-primary)" }}>
                          Statutory Assessment & Rule Reference
                        </span>
                        <span
                          style={{
                            fontFamily: "monospace",
                            fontWeight: "600",
                            fontSize: "11px",
                            color: "var(--accent)",
                            background: "#eff6ff",
                            padding: "2px 6px",
                            borderRadius: "4px",
                          }}
                        >
                          {itcResult.rule_reference}
                        </span>
                      </div>
                      <div style={{ color: "var(--text-secondary)" }}>
                        {itcResult.reason}
                      </div>
                    </div>

                    {/* Line-item ITC Breakdown Table */}
                    {itcResult.line_item_breakdown && itcResult.line_item_breakdown.length > 1 && (
                      <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", fontSize: "11px", borderCollapse: "collapse", textAlign: "left" }}>
                          <thead>
                            <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", background: "var(--bg-main)" }}>
                              <th style={{ padding: "6px" }}>#</th>
                              <th style={{ padding: "6px" }}>Item Description</th>
                              <th style={{ padding: "6px" }}>Account</th>
                              <th style={{ padding: "6px", textAlign: "right" }}>Tax (₹)</th>
                              <th style={{ padding: "6px", textAlign: "center" }}>Status</th>
                              <th style={{ padding: "6px" }}>Rule & Reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            {itcResult.line_item_breakdown.map((line) => (
                              <tr key={line.line_index} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                                <td style={{ padding: "6px", color: "var(--text-secondary)" }}>{line.line_index}</td>
                                <td style={{ padding: "6px", fontWeight: "600" }}>{line.description}</td>
                                <td style={{ padding: "6px", color: "var(--text-secondary)" }}>{line.account_name || "-"}</td>
                                <td style={{ padding: "6px", textAlign: "right", fontFamily: "monospace" }}>
                                  ₹{line.tax_amount?.toLocaleString() || "0.00"}
                                </td>
                                <td style={{ padding: "6px", textAlign: "center" }}>
                                  <span
                                    className={`badge ${
                                      line.itc_status === "ELIGIBLE"
                                        ? "badge-success"
                                        : line.itc_status === "INELIGIBLE"
                                        ? "badge-warning"
                                        : "badge-uploaded"
                                    }`}
                                    style={{ fontSize: "10px" }}
                                  >
                                    {line.itc_status}
                                  </span>
                                </td>
                                <td style={{ padding: "6px", fontSize: "10px", color: "var(--text-secondary)" }}>
                                  <strong style={{ color: "var(--text-primary)" }}>{line.rule_reference}:</strong> {line.reason}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>
                )}

                {/* 11. FINANCIAL VALIDATION & RECONCILIATION (STAGE 5 DETERMINISTIC ENGINE) */}
                {financialValidationResult && (
                  <section
                    style={{
                      borderTop: "1px solid var(--border-subtle)",
                      paddingTop: "18px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "12px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Calculator size={16} color="var(--accent)" />
                        <h3
                          style={{
                            fontSize: "14px",
                            fontWeight: "700",
                            letterSpacing: "0.02em",
                            textTransform: "uppercase",
                          }}
                        >
                          11. Financial Validation & Reconciliation
                        </h3>
                      </div>
                      <span
                        className={`badge ${
                          financialValidationResult.overall_status === "PASSED"
                            ? "badge-success"
                            : financialValidationResult.overall_status === "MISMATCH"
                            ? "badge-danger"
                            : "badge-warning"
                        }`}
                        style={{ fontSize: "11px", fontWeight: "700" }}
                      >
                        {financialValidationResult.overall_status === "PASSED"
                          ? "✓ RECONCILED (PASSED)"
                          : financialValidationResult.overall_status === "MISMATCH"
                          ? "⚠ DISCREPANCY DETECTED"
                          : "REVIEW REQUIRED"}
                      </span>
                    </div>

                    {/* Financial Summary Cards */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(3, 1fr)",
                        gap: "12px",
                        marginBottom: "14px",
                      }}
                    >
                      {/* Subtotal Card */}
                      <div
                        style={{
                          background: "var(--bg-main)",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border-subtle)",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          Subtotal (Taxable)
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                          <span style={{ fontWeight: "700", fontSize: "15px" }}>
                            ₹{financialValidationResult.source.subtotal?.toLocaleString() ?? "-"}
                          </span>
                          <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                            Calc: ₹{financialValidationResult.calculated.subtotal?.toLocaleString() ?? "-"}
                          </span>
                        </div>
                        {financialValidationResult.differences?.subtotal !== undefined && financialValidationResult.differences?.subtotal !== null && financialValidationResult.differences?.subtotal !== 0 && (
                          <div style={{ fontSize: "10px", color: "var(--danger)", fontWeight: "600", marginTop: "2px" }}>
                            Diff: ₹{financialValidationResult.differences.subtotal.toLocaleString()}
                          </div>
                        )}
                      </div>

                      {/* GST / Tax Total Card */}
                      <div
                        style={{
                          background: "var(--bg-main)",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border-subtle)",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "3px" }}>
                          GST Tax Total
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                          <span style={{ fontWeight: "700", fontSize: "15px" }}>
                            ₹{financialValidationResult.source.tax_total?.toLocaleString() ?? "-"}
                          </span>
                          <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                            Calc: ₹{financialValidationResult.calculated.gst_total?.toLocaleString() ?? "-"}
                          </span>
                        </div>
                        {financialValidationResult.differences?.tax_total !== undefined && financialValidationResult.differences?.tax_total !== null && financialValidationResult.differences?.tax_total !== 0 && (
                          <div style={{ fontSize: "10px", color: "var(--danger)", fontWeight: "600", marginTop: "2px" }}>
                            Diff: ₹{financialValidationResult.differences.tax_total.toLocaleString()}
                          </div>
                        )}
                      </div>

                      {/* Grand Total Card */}
                      <div
                        style={{
                          background: financialValidationResult.differences?.total_amount ? "#fef2f2" : "#f0fdf4",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: financialValidationResult.differences?.total_amount ? "1px solid #fecaca" : "1px solid #bbf7d0",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: financialValidationResult.differences?.total_amount ? "#991b1b" : "#166534", marginBottom: "3px" }}>
                          Grand Total Equation
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                          <span style={{ fontWeight: "700", fontSize: "15px", color: financialValidationResult.differences?.total_amount ? "#b91c1c" : "#15803d" }}>
                            ₹{financialValidationResult.source.total_amount?.toLocaleString() ?? "-"}
                          </span>
                          <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                            Expected: ₹{financialValidationResult.calculated.grand_total?.toLocaleString() ?? "-"}
                          </span>
                        </div>
                        {financialValidationResult.differences?.total_amount !== undefined && financialValidationResult.differences?.total_amount !== null && financialValidationResult.differences?.total_amount !== 0 && (
                          <div style={{ fontSize: "10px", color: "#b91c1c", fontWeight: "700", marginTop: "2px" }}>
                            Diff: ₹{financialValidationResult.differences.total_amount.toLocaleString()}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Secondary Charges Strip */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(4, 1fr)",
                        gap: "8px",
                        background: "var(--bg-main)",
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        fontSize: "11px",
                        marginBottom: "14px",
                      }}
                    >
                      <div>
                        <span style={{ color: "var(--text-secondary)" }}>Discount: </span>
                        <strong>-₹{financialValidationResult.source.discount_total?.toLocaleString() || "0.00"}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--text-secondary)" }}>Shipping: </span>
                        <strong>+₹{financialValidationResult.source.shipping_charges?.toLocaleString() || "0.00"}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--text-secondary)" }}>Other Charges: </span>
                        <strong>+₹{financialValidationResult.source.other_charges?.toLocaleString() || "0.00"}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--text-secondary)" }}>Round Off: </span>
                        <strong>{financialValidationResult.source.round_off !== null && financialValidationResult.source.round_off !== undefined ? (financialValidationResult.source.round_off >= 0 ? `+₹${financialValidationResult.source.round_off}` : `-₹${Math.abs(financialValidationResult.source.round_off)}`) : "₹0.00"}</strong>
                      </div>
                    </div>

                    {/* Mathematical Checks Table */}
                    <div style={{ overflowX: "auto", marginBottom: "12px" }}>
                      <table style={{ width: "100%", fontSize: "11px", borderCollapse: "collapse", textAlign: "left" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", background: "var(--bg-main)" }}>
                            <th style={{ padding: "8px" }}>Mathematical Check</th>
                            <th style={{ padding: "8px", textAlign: "right" }}>Extracted (Source)</th>
                            <th style={{ padding: "8px", textAlign: "right" }}>Calculated (Engine)</th>
                            <th style={{ padding: "8px", textAlign: "right" }}>Difference</th>
                            <th style={{ padding: "8px", textAlign: "center" }}>Status</th>
                            <th style={{ padding: "8px" }}>Notes / Discrepancies</th>
                          </tr>
                        </thead>
                        <tbody>
                          {financialValidationResult.checks?.map((chk, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                              <td style={{ padding: "8px", fontWeight: "600" }}>{chk.description || chk.name}</td>
                              <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                                {chk.source_value !== null && chk.source_value !== undefined ? `₹${chk.source_value.toLocaleString()}` : "-"}
                              </td>
                              <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace" }}>
                                {chk.calculated_value !== null && chk.calculated_value !== undefined ? `₹${chk.calculated_value.toLocaleString()}` : "-"}
                              </td>
                              <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace", color: chk.difference && chk.difference > 0 ? "var(--danger)" : "var(--text-primary)" }}>
                                {chk.difference !== null && chk.difference !== undefined ? `₹${chk.difference.toLocaleString()}` : "₹0.00"}
                              </td>
                              <td style={{ padding: "8px", textAlign: "center" }}>
                                <span
                                  className={`badge ${
                                    chk.status === "PASSED"
                                      ? "badge-success"
                                      : chk.status === "MISMATCH"
                                      ? "badge-danger"
                                      : chk.status === "NOT_APPLICABLE"
                                      ? "badge-uploaded"
                                      : "badge-warning"
                                  }`}
                                  style={{ fontSize: "10px" }}
                                >
                                  {chk.status}
                                </span>
                              </td>
                              <td style={{ padding: "8px", color: "var(--text-secondary)", fontSize: "10px" }}>
                                {chk.note || (chk.status === "PASSED" ? "Verified consistent" : "")}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Discrepancy Errors & Warnings Callout */}
                    {financialValidationResult.errors && financialValidationResult.errors.length > 0 && (
                      <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "var(--radius-sm)", padding: "10px 14px", marginBottom: "8px", fontSize: "12px", color: "#991b1b" }}>
                        <div style={{ fontWeight: "700", marginBottom: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
                          <AlertCircle size={15} /> <span>Mathematical Discrepancies Detected:</span>
                        </div>
                        {financialValidationResult.errors.map((err, i) => (
                          <div key={i} style={{ marginLeft: "21px", marginBottom: i < financialValidationResult.errors.length - 1 ? "4px" : "0" }}>
                            • {err}
                          </div>
                        ))}
                      </div>
                    )}
                    {financialValidationResult.warnings && financialValidationResult.warnings.length > 0 && (
                      <div style={{ background: "#fefce8", border: "1px solid #fef08a", borderRadius: "var(--radius-sm)", padding: "10px 14px", fontSize: "12px", color: "#854d0e" }}>
                        {financialValidationResult.warnings.map((w, i) => (
                          <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: i < financialValidationResult.warnings!.length - 1 ? "4px" : "0" }}>
                            <AlertCircle size={14} /> <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                )}

                {/* 12. ACCOUNTING JOURNAL ENTRY PREVIEW (STAGE 6 DETERMINISTIC ENGINE) */}
                {journalEntry && (
                  <section
                    style={{
                      borderTop: "1px solid var(--border-subtle)",
                      paddingTop: "18px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "12px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <BookOpen size={16} color="var(--accent)" />
                        <h3
                          style={{
                            fontSize: "14px",
                            fontWeight: "700",
                            letterSpacing: "0.02em",
                            textTransform: "uppercase",
                          }}
                        >
                          12. Accounting Journal Entry Preview (Double-Entry)
                        </h3>
                      </div>
                      <span
                        className={`badge ${
                          journalEntry.status === "BALANCED"
                            ? "badge-success"
                            : journalEntry.status === "UNBALANCED"
                            ? "badge-danger"
                            : "badge-warning"
                        }`}
                        style={{ fontSize: "11px", fontWeight: "700" }}
                      >
                        {journalEntry.status === "BALANCED"
                          ? "✓ BALANCED"
                          : journalEntry.status === "UNBALANCED"
                          ? "✕ UNBALANCED"
                          : "⚠ REVIEW REQUIRED"}
                      </span>
                    </div>

                    {/* Journal Balancing Metrics */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(3, 1fr)",
                        gap: "12px",
                        marginBottom: "14px",
                      }}
                    >
                      <div
                        style={{
                          background: "#f0fdf4",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid #bbf7d0",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: "#166534", marginBottom: "3px" }}>
                          Total Debits (Dr)
                        </div>
                        <div style={{ fontWeight: "700", fontSize: "16px", color: "#15803d", fontFamily: "monospace" }}>
                          ₹{journalEntry.total_debit?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
                        </div>
                      </div>

                      <div
                        style={{
                          background: "#f0fdf4",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid #bbf7d0",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: "#166534", marginBottom: "3px" }}>
                          Total Credits (Cr)
                        </div>
                        <div style={{ fontWeight: "700", fontSize: "16px", color: "#15803d", fontFamily: "monospace" }}>
                          ₹{journalEntry.total_credit?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
                        </div>
                      </div>

                      <div
                        style={{
                          background: journalEntry.difference !== 0 ? "#fef2f2" : "var(--bg-main)",
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          border: journalEntry.difference !== 0 ? "1px solid #fecaca" : "1px solid var(--border-subtle)",
                        }}
                      >
                        <div style={{ fontSize: "11px", color: journalEntry.difference !== 0 ? "#991b1b" : "var(--text-secondary)", marginBottom: "3px" }}>
                          Balancing Net Difference
                        </div>
                        <div style={{ fontWeight: "700", fontSize: "16px", color: journalEntry.difference !== 0 ? "#b91c1c" : "var(--text-primary)", fontFamily: "monospace" }}>
                          ₹{journalEntry.difference?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
                        </div>
                      </div>
                    </div>

                    {/* Journal Lines Table (Read-Only Preview) */}
                    <div style={{ overflowX: "auto", marginBottom: "12px" }}>
                      <table style={{ width: "100%", fontSize: "11px", borderCollapse: "collapse", textAlign: "left" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", background: "var(--bg-main)" }}>
                            <th style={{ padding: "8px", width: "30px" }}>#</th>
                            <th style={{ padding: "8px" }}>Account Name</th>
                            <th style={{ padding: "8px" }}>Account Code</th>
                            <th style={{ padding: "8px" }}>Type</th>
                            <th style={{ padding: "8px", textAlign: "right" }}>Debit (₹)</th>
                            <th style={{ padding: "8px", textAlign: "right" }}>Credit (₹)</th>
                            <th style={{ padding: "8px" }}>Source / Provenance</th>
                            <th style={{ padding: "8px" }}>Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {journalEntry.lines?.map((line, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                              <td style={{ padding: "8px", color: "var(--text-secondary)" }}>{idx + 1}</td>
                              <td style={{ padding: "8px", fontWeight: "600", color: "var(--text-primary)" }}>
                                {line.account_name}
                              </td>
                              <td style={{ padding: "8px", fontFamily: "monospace", color: "var(--accent)" }}>
                                {line.account_id}
                              </td>
                              <td style={{ padding: "8px" }}>
                                <span
                                  className={`badge ${
                                    line.line_type === "INPUT_TAX"
                                      ? "badge-uploaded"
                                      : line.line_type === "ACCOUNTS_PAYABLE"
                                      ? "badge-warning"
                                      : line.line_type === "TDS_PAYABLE"
                                      ? "badge-danger"
                                      : "badge-success"
                                  }`}
                                  style={{ fontSize: "10px" }}
                                >
                                  {line.line_type}
                                </span>
                              </td>
                              <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace", fontWeight: line.debit > 0 ? "700" : "normal" }}>
                                {line.debit > 0 ? `₹${line.debit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "-"}
                              </td>
                              <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace", fontWeight: line.credit > 0 ? "700" : "normal" }}>
                                {line.credit > 0 ? `₹${line.credit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "-"}
                              </td>
                              <td style={{ padding: "8px", fontSize: "10px", color: "var(--text-secondary)" }}>
                                <span
                                  style={{
                                    fontFamily: "monospace",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    background: line.provenance === "HITL_OVERRIDE" ? "#fef3c7" : "#f1f5f9",
                                    color: line.provenance === "HITL_OVERRIDE" ? "#92400e" : "var(--text-secondary)",
                                    fontWeight: "600",
                                  }}
                                >
                                  {line.provenance}
                                </span>
                              </td>
                              <td style={{ padding: "8px", color: "var(--text-secondary)", fontSize: "11px" }}>
                                {line.description || "-"}
                              </td>
                            </tr>
                          ))}
                          <tr style={{ background: "var(--bg-main)", fontWeight: "700", borderTop: "2px solid var(--border-subtle)" }}>
                            <td colSpan={4} style={{ padding: "8px", textAlign: "right" }}>
                              Total (INR)
                            </td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace", color: "#15803d" }}>
                              ₹{journalEntry.total_debit?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
                            </td>
                            <td style={{ padding: "8px", textAlign: "right", fontFamily: "monospace", color: "#15803d" }}>
                              ₹{journalEntry.total_credit?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
                            </td>
                            <td colSpan={2} style={{ padding: "8px", fontSize: "10px", color: "var(--text-secondary)" }}>
                              {journalEntry.validation?.balanced ? "✓ Reconciled & Balanced" : "⚠ Review Discrepancy"}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* Journal Errors and Warnings */}
                    {journalEntry.validation?.errors && journalEntry.validation.errors.length > 0 && (
                      <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "var(--radius-sm)", padding: "10px 14px", marginBottom: "8px", fontSize: "12px", color: "#991b1b" }}>
                        <div style={{ fontWeight: "700", marginBottom: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
                          <AlertCircle size={15} /> <span>Journal Balancing Issues:</span>
                        </div>
                        {journalEntry.validation.errors.map((err, i) => (
                          <div key={i} style={{ marginLeft: "21px", marginBottom: i < journalEntry.validation.errors.length - 1 ? "4px" : "0" }}>
                            • {err}
                          </div>
                        ))}
                      </div>
                    )}
                    {journalEntry.validation?.warnings && journalEntry.validation.warnings.length > 0 && (
                      <div style={{ background: "#fefce8", border: "1px solid #fef08a", borderRadius: "var(--radius-sm)", padding: "10px 14px", fontSize: "12px", color: "#854d0e" }}>
                        {journalEntry.validation.warnings.map((w, i) => (
                          <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: i < journalEntry.validation.warnings.length - 1 ? "4px" : "0" }}>
                            <AlertCircle size={14} /> <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                )}

                {/* 13. ADDITIONAL EXTRACTED INFORMATION (ZERO DATA LOSS) */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                    <Layers size={16} color="var(--text-secondary)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      13. Additional Extracted Information
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

                {/* 12. SAVE CHANGES (WORKING BUTTON) */}
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
                  <span className="badge badge-uploaded" style={{ background: "#e8f4fd", color: "#0066cc", border: "1px solid #cce5ff" }}>
                    {exportedInvoices.length}
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "300px", overflowY: "auto" }}>
                  {exportedInvoices.length > 0 ? (
                    exportedInvoices.map((item) => (
                      <div
                        key={item.id}
                        onClick={() => router.push(`/finance/invoices/${item.id}`)}
                        style={{
                          padding: "12px",
                          borderRadius: "var(--radius-sm)",
                          background: item.id === invoiceId ? "#f0f7ff" : "var(--bg-main)",
                          border: item.id === invoiceId ? "1px solid var(--accent)" : "1px solid var(--border-subtle)",
                          cursor: "pointer",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                          <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-primary)" }}>
                            {item.zoho_bill_number ? `Bill #${item.zoho_bill_number}` : (item.invoice_number ? `INV #${item.invoice_number}` : item.file_name)}
                          </span>
                          {item.total_amount && (
                            <span style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-primary)" }}>
                              ₹{item.total_amount.toLocaleString()}
                            </span>
                          )}
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: "var(--text-secondary)" }}>
                          <span>{item.vendor_name || item.file_name}</span>
                          <span className="badge" style={{ fontSize: "10px", background: "#e8f4fd", color: "#0066cc", border: "1px solid #cce5ff" }}>
                            ZOHO BILL ✓
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: "36px 16px",
                        textAlign: "center",
                        color: "var(--text-secondary)",
                      }}
                    >
                      <Send size={24} color="var(--text-tertiary)" style={{ marginBottom: "8px", opacity: 0.5 }} />
                      <div style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-secondary)" }}>
                        No invoices exported yet.
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                        Approve an invoice and click "Export to Zoho" to sync.
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}

      {/* Rejection Modal Dialog */}
      {rejectModalOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.4)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: "#ffffff",
              borderRadius: "var(--radius-md)",
              padding: "24px",
              width: "100%",
              maxWidth: "460px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
              <div style={{ padding: "8px", background: "#fef2f2", borderRadius: "50%", color: "var(--danger)" }}>
                <AlertTriangle size={20} />
              </div>
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-primary)" }}>
                Reject Invoice
              </h3>
            </div>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "16px" }}>
              Please specify the reason for rejecting this invoice. This will be permanently recorded in the audit trail.
            </p>
            <textarea
              className="form-input"
              rows={3}
              placeholder="e.g. Incorrect GSTIN, missing PO number, or price mismatch..."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              style={{ width: "100%", marginBottom: "18px", fontSize: "13px" }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setRejectModalOpen(false)}
                className="btn btn-secondary"
                style={{ padding: "8px 16px", fontSize: "13px" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRejectConfirm}
                disabled={isRejecting || !rejectReason.trim()}
                className="btn btn-primary"
                style={{
                  padding: "8px 16px",
                  fontSize: "13px",
                  background: "var(--danger)",
                  borderColor: "var(--danger)",
                }}
              >
                {isRejecting ? "Rejecting..." : "Confirm Rejection"}
              </button>
            </div>
          </div>
        </div>
      )}

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

      {/* Reject Modal */}
      {rejectModalOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            backdropFilter: "blur(4px)",
          }}
        >
          <div
            className="card"
            style={{
              width: "100%",
              maxWidth: "460px",
              padding: "24px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.15)",
              background: "#ffffff",
            }}
          >
            <h3 style={{ fontSize: "17px", fontWeight: "700", marginBottom: "8px", color: "var(--danger)" }}>
              Reject Invoice
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "16px" }}>
              Please provide a reason for rejecting this invoice.
            </p>
            <textarea
              className="form-input"
              rows={3}
              value={rejectReason}
              placeholder="e.g. Incorrect tax invoice calculation or invalid vendor PAN..."
              onChange={(e) => setRejectReason(e.target.value)}
              style={{ width: "100%", marginBottom: "20px" }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setRejectModalOpen(false)}
                className="btn btn-secondary"
                disabled={isRejecting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRejectConfirm}
                disabled={isRejecting || !rejectReason.trim()}
                className="btn btn-primary"
                style={{ background: "var(--danger)", borderColor: "var(--danger)" }}
              >
                {isRejecting ? "Rejecting..." : "Confirm Rejection"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
