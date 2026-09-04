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
  approveJournal,
  approveTds,
  rejectInvoice,
  exportInvoiceToZoho,
  getZohoMasterData,
  getInvoiceVendorStatus,
  addVendorToZoho,
  InvoiceVendorStatusResponse,
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
  getHitlExtraction,
  approveHitlExtraction,
  getHitlFinal,
  approveHitlFinal,
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
  AlertTriangle,
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

// Helper to format ISO YYYY-MM-DD or arbitrary dates into DD/MM/YYYY
function formatToIndianDate(val: any): string {
  if (!val || typeof val !== "string") return val ? String(val) : "";
  const s = val.trim();
  // If already DD/MM/YYYY
  if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(s)) return s;
  // If YYYY-MM-DD or YYYY/MM/DD
  const iso = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
  if (iso) {
    const y = iso[1];
    const m = iso[2].padStart(2, "0");
    const d = iso[3].padStart(2, "0");
    return `${d}/${m}/${y}`;
  }
  return s;
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

interface InvoiceWorkspaceProps {
  mode?: "internal" | "customer" | "hitl_extraction" | "hitl_final";
  invoiceId?: string;
}

export default function InvoiceWorkspace({
  mode = "internal",
  invoiceId: propInvoiceId,
}: InvoiceWorkspaceProps) {
  const params = useParams();
  const router = useRouter();
  const invoiceId = propInvoiceId || (params?.id as string);

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [workflowInvoices, setWorkflowInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isCategorizing, setIsCategorizing] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isHitlApproving, setIsHitlApproving] = useState(false);
  const [isApprovingJournal, setIsApprovingJournal] = useState(false);
  const [isApprovingTds, setIsApprovingTds] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [journalPreview, setJournalPreview] = useState<JournalPreviewResponse | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Editable form state
  const [formData, setFormData] = useState<ExtractedInvoiceData>({});
  const [accountingData, setAccountingData] = useState<AccountingOutput>({});
  const [gstResult, setGstResult] = useState<GstResult | null>(null);
  const [itcResult, setItcResult] = useState<ItcResult | null>(null);
  const [financialValidationResult, setFinancialValidationResult] = useState<FinancialValidationResult | null>(null);
  const [journalEntry, setJournalEntry] = useState<JournalEntry | null>(null);
  const [additionalFieldsText, setAdditionalFieldsText] = useState<string>("");
  const [zohoAccounts, setZohoAccounts] = useState<any[]>([]);
  const [showRawJsonModal, setShowRawJsonModal] = useState<boolean>(false);
  const [copiedJson, setCopiedJson] = useState<boolean>(false);
  const [warningModalOpen, setWarningModalOpen] = useState<boolean>(false);
  const [activeWarnings, setActiveWarnings] = useState<string[]>([]);
  const [vendorStatus, setVendorStatus] = useState<InvoiceVendorStatusResponse | null>(null);
  const [vendorModalOpen, setVendorModalOpen] = useState<boolean>(false);
  const [isAddingVendor, setIsAddingVendor] = useState<boolean>(false);

  // Closed Accounting Period State
  const [postingDate, setPostingDate] = useState<string>("");
  const [periodResolution, setPeriodResolution] = useState<string>("NONE");
  const [periodReason, setPeriodReason] = useState<string>("");
  const [booksClosedDate, setBooksClosedDate] = useState<string | null>(null);
  const [periodInfo, setPeriodInfo] = useState<any>(null);
  const [periodModalOpen, setPeriodModalOpen] = useState<boolean>(false);

  useEffect(() => {
    if (!invoiceId) return;

    async function loadData() {
      try {
        setLoading(true);
        const fetchInvoicePromise =
          mode === "hitl_extraction"
            ? getHitlExtraction(invoiceId)
            : mode === "hitl_final"
            ? getHitlFinal(invoiceId)
            : getInvoice(invoiceId);

        // 1. Fetch invoice first for instant rendering (<50ms)
        const invData = await fetchInvoicePromise;
        setInvoice(invData);
        setBooksClosedDate(invData.books_closed_through_date || null);
        setPeriodInfo(invData.period_info || null);
        setPeriodResolution(invData.period_resolution || "NONE");
        setPeriodReason(invData.period_resolution_reason || "");
        setPostingDate(invData.posting_date || invData.document_date || "");

        // 2. Fetch Zoho master data and sidebar list in background without blocking UI
        getZohoMasterData()
          .then((m) => setZohoAccounts(m.accounts || []))
          .catch(() => null);
        listInvoices()
          .then(setWorkflowInvoices)
          .catch(() => null);
        getJournalPreview(invoiceId)
          .then(setJournalPreview)
          .catch(() => null);
        getInvoiceVendorStatus(invoiceId)
          .then(setVendorStatus)
          .catch(() => null);

        // If still in initial stages, route to processing page (only in standard user modes)
        if (
          mode !== "hitl_extraction" &&
          mode !== "hitl_final" &&
          (invData.status === "PENDING" ||
            invData.status === "PROCESSING_VLM" ||
            invData.status === "PROCESSING_ACCOUNTING")
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

        const rawF: any = (rawData as any).raw_fields || (currData as any).raw_fields || {};

        // Deep resolve vendor / customer fields from raw_fields if cleared or null
        if (!extracted.vendor_gstin && rawF.vendor_gstin) {
          extracted.vendor_gstin = rawF.vendor_gstin;
        }
        if (!extracted.vendor_pan && rawF.vendor_pan) {
          extracted.vendor_pan = rawF.vendor_pan;
        } else if (!extracted.vendor_pan && extracted.vendor_gstin && extracted.vendor_gstin.length === 15) {
          extracted.vendor_pan = extracted.vendor_gstin.substring(2, 12);
        }

        if (!extracted.customer_gstin && rawF.customer_gstin) {
          extracted.customer_gstin = rawF.customer_gstin;
        }
        if (!extracted.customer_pan && rawF.customer_pan) {
          extracted.customer_pan = rawF.customer_pan;
        } else if (!extracted.customer_pan && extracted.customer_gstin && extracted.customer_gstin.length === 15) {
          extracted.customer_pan = extracted.customer_gstin.substring(2, 12);
        }

        if (!extracted.place_of_supply && rawF.place_of_supply) {
          extracted.place_of_supply = rawF.place_of_supply;
        } else if (!extracted.place_of_supply) {
          if (extracted.vendor_gstin?.startsWith("36") || extracted.customer_gstin?.startsWith("36")) {
            extracted.place_of_supply = "36-Telangana";
          } else if (extracted.vendor_gstin?.startsWith("27") || extracted.customer_gstin?.startsWith("27")) {
            extracted.place_of_supply = "27-Maharashtra";
          } else if (extracted.vendor_gstin?.startsWith("29") || extracted.customer_gstin?.startsWith("29")) {
            extracted.place_of_supply = "29-Karnataka";
          }
        }

        if (!extracted.payment_terms && rawF.payment_terms) {
          extracted.payment_terms = rawF.payment_terms;
        }
        if (!extracted.vendor_email && rawF.vendor_email) {
          extracted.vendor_email = rawF.vendor_email;
        }
        if (!extracted.vendor_address && rawF.vendor_address) {
          extracted.vendor_address = rawF.vendor_address;
        }
        if (!extracted.customer_address && rawF.customer_address) {
          extracted.customer_address = rawF.customer_address;
        }

        if (extracted.invoice_date) {
          extracted.invoice_date = formatToIndianDate(extracted.invoice_date);
        } else if (rawF.invoice_date) {
          extracted.invoice_date = formatToIndianDate(rawF.invoice_date);
        }
        if (extracted.due_date) {
          extracted.due_date = formatToIndianDate(extracted.due_date);
        } else if (rawF.due_date) {
          extracted.due_date = formatToIndianDate(rawF.due_date);
        }

        const rawItems = Array.isArray(currData.line_items) && currData.line_items.length > 0
          ? currData.line_items
          : Array.isArray(rawData.line_items) && rawData.line_items.length > 0
          ? rawData.line_items
          : [];

        extracted.line_items = rawItems.map((item: any, pos: number) => {
          const it = { ...item };
          const itRf = it.raw_fields || {};
          if (!it.hsn_code && itRf.hsn_code) it.hsn_code = itRf.hsn_code;
          if (!it.description && itRf.description) it.description = itRf.description;
          if (it.quantity === undefined || it.quantity === null) {
            if (itRf.quantity) {
              const qVal = parseFloat(String(itRf.quantity).replace(/,/g, ""));
              if (!isNaN(qVal)) it.quantity = qVal;
            }
          }
          if (it.unit_price === undefined || it.unit_price === null) {
            if (itRf.unit_price) {
              const uVal = parseFloat(String(itRf.unit_price).replace(/,/g, ""));
              if (!isNaN(uVal)) it.unit_price = uVal;
            }
          }
          if (it.taxable_amount === undefined || it.taxable_amount === null) {
            if (itRf.taxable_amount) {
              const tVal = parseFloat(String(itRf.taxable_amount).replace(/,/g, ""));
              if (!isNaN(tVal)) it.taxable_amount = tVal;
            }
          }
          if (it.taxable_amount === undefined || it.taxable_amount === null) {
            if (it.quantity && it.unit_price) it.taxable_amount = it.quantity * it.unit_price;
          }
          if (it.total === undefined || it.total === null) {
            it.total = (it.taxable_amount || 0) + (it.cgst_amount || 0) + (it.sgst_amount || 0) + (it.igst_amount || 0);
          }
          it.line_index = it.line_index || pos + 1;
          return it;
        });

        if (extracted.subtotal === undefined || extracted.subtotal === null) {
          if (rawData.subtotal !== undefined && rawData.subtotal !== null) {
            extracted.subtotal = rawData.subtotal;
          } else if (rawF.subtotal) {
            const sVal = parseFloat(String(rawF.subtotal).replace(/[^0-9.-]+/g, ""));
            if (!isNaN(sVal)) extracted.subtotal = sVal;
          }
        }
        if (extracted.tax_total === undefined || extracted.tax_total === null) {
          if (rawData.tax_total !== undefined && rawData.tax_total !== null) {
            extracted.tax_total = rawData.tax_total;
          } else if (rawF.tax_total) {
            const tVal = parseFloat(String(rawF.tax_total).replace(/[^0-9.-]+/g, ""));
            if (!isNaN(tVal)) extracted.tax_total = tVal;
          }
        }
        if (extracted.total_amount === undefined || extracted.total_amount === null) {
          if (rawData.total_amount !== undefined && rawData.total_amount !== null) {
            extracted.total_amount = rawData.total_amount;
          } else if (rawF.total_amount) {
            const totVal = parseFloat(String(rawF.total_amount).replace(/[^0-9.-]+/g, ""));
            if (!isNaN(totVal)) extracted.total_amount = totVal;
          }
        }

        // Deep resolve Bank Details (parsing structured object or unparsed text)
        const bankObj: any = { 
          ...(typeof rawData.bank_details === "object" ? rawData.bank_details : {}), 
          ...(typeof currData.bank_details === "object" ? currData.bank_details : {}) 
        };
        const unparsedBankText: string = 
          (typeof rawF.bank_details === "string" ? rawF.bank_details : "") || 
          (rawData.additional_fields as any)?.unparsed_bank_details || 
          (currData.additional_fields as any)?.unparsed_bank_details || 
          (typeof rawData.bank_details === "string" ? rawData.bank_details : "") || 
          "";

        if (unparsedBankText) {
          if (!bankObj.bank_name) {
            const m = unparsedBankText.match(/Bank:\s*([^,|]+)/i);
            if (m) bankObj.bank_name = m[1].trim();
          }
          if (!bankObj.branch_name) {
            const m = unparsedBankText.match(/Branch[:\s]*([^|]+)/i) || unparsedBankText.match(/Bank:[^,]+,\s*([^|]+)/i);
            if (m) bankObj.branch_name = m[1].trim();
          }
          if (!bankObj.account_number) {
            const m = unparsedBankText.match(/(?:A\/C\s*No|Account\s*No|A\/c|Account)[:.\s]*([0-9A-Za-z]+)/i);
            if (m) bankObj.account_number = m[1].trim();
          }
          if (!bankObj.ifsc_code) {
            const m = unparsedBankText.match(/IFSC[:.\s]*([A-Z]{4}0[A-Z0-9]{6})/i);
            if (m) bankObj.ifsc_code = m[1].trim();
          }
          if (!bankObj.account_holder_name) {
            const m = unparsedBankText.match(/Account\s*Name[:.\s]*([^|]+)/i);
            if (m) bankObj.account_holder_name = m[1].trim();
          }
        }
        extracted.bank_details = bankObj;

        if (!extracted.currency && (rawData.currency || rawF.currency)) {
          extracted.currency = rawData.currency || rawF.currency;
        }
        if (!extracted.po_number && (rawData.po_number || rawF.po_number)) {
          extracted.po_number = rawData.po_number || rawF.po_number;
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
  const isPdf =
    invoice?.mime_type === "application/pdf" ||
    Boolean(invoice?.file_name?.toLowerCase().endsWith(".pdf")) ||
    Boolean(invoice?.file_path?.toLowerCase().endsWith(".pdf")) ||
    (!invoice?.mime_type?.startsWith("image/") && !invoice?.file_name?.match(/\.(png|jpg|jpeg|webp)$/i));

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
    setAccountingData((prev: any) => {
      const list = [...(prev.accounting || [])];
      const newIdx = list.length + 1;
      const defaultId = zohoAccounts?.[0]?.zoho_account_id || `ACC_${newIdx}`;
      const defaultName = zohoAccounts?.[0]?.account_name || "General Expenses";
      list.push({
        line_index: newIdx,
        source_description: "",
        account_id: defaultId,
        account_name: defaultName,
        approved_account_id: defaultId,
        approved_account_name: defaultName,
        final_account_id: defaultId,
        final_account_name: defaultName,
      });
      return { ...prev, accounting: list };
    });
  };

  const removeLineItem = (index: number) => {
    setFormData((prev) => {
      const items = [...(prev.line_items || [])];
      items.splice(index, 1);
      return { ...prev, line_items: items };
    });
    setAccountingData((prev: any) => {
      const list = [...(prev.accounting || [])];
      list.splice(index, 1);
      // Re-index line_index
      const reindexed = list.map((item, idx) => ({ ...item, line_index: idx + 1 }));
      return { ...prev, accounting: reindexed };
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

  // Journal line editing helpers
  const handleJournalLineChange = (
    index: number,
    field: string,
    value: any
  ) => {
    setJournalEntry((prev: any) => {
      if (!prev) return prev;
      const lines = [...(prev.lines || [])];
      const updatedLine = { ...lines[index], [field]: value, provenance: mode === "customer" ? "CUSTOMER_EDIT" : "HITL_OVERRIDE" };
      lines[index] = updatedLine;

      // Recalculate totals
      let totalDr = 0;
      let totalCr = 0;
      lines.forEach((l: any) => {
        totalDr += typeof l.debit === "number" ? l.debit : parseFloat(l.debit) || 0;
        totalCr += typeof l.credit === "number" ? l.credit : parseFloat(l.credit) || 0;
      });
      totalDr = Math.round(totalDr * 100) / 100;
      totalCr = Math.round(totalCr * 100) / 100;
      const diff = Math.round(Math.abs(totalDr - totalCr) * 100) / 100;
      const isBalanced = diff <= 0.05 && totalDr > 0;

      return {
        ...prev,
        lines,
        total_debit: totalDr,
        total_credit: totalCr,
        difference: diff,
        is_balanced: isBalanced,
        validation: {
          ...(prev.validation || {}),
          balanced: isBalanced,
          errors: isBalanced ? [] : [`Journal unbalanced: Debit ₹${totalDr} vs Credit ₹${totalCr} (Difference ₹${diff})`],
        },
      };
    });
  };

  const addJournalLine = () => {
    setJournalEntry((prev: any) => {
      const defaultId = zohoAccounts?.[0]?.zoho_account_id || "ACC_MANUAL";
      const defaultName = zohoAccounts?.[0]?.account_name || "General Expenses";
      const newLine = {
        account_id: defaultId,
        account_name: defaultName,
        line_type: "EXPENSE",
        debit: 0,
        credit: 0,
        source_line_index: null,
        provenance: mode === "customer" ? "CUSTOMER_EDIT" : "HITL_OVERRIDE",
        description: "Manual journal line adjustment",
      };
      const lines = [...(prev?.lines || []), newLine];
      return {
        ...prev,
        status: "REVIEW_REQUIRED",
        lines,
        total_debit: prev?.total_debit || 0,
        total_credit: prev?.total_credit || 0,
        difference: prev?.difference || 0,
        currency: prev?.currency || "INR",
        validation: prev?.validation || { balanced: false, tolerance: 0.05, errors: [], warnings: [] },
      };
    });
  };

  const removeJournalLine = (index: number) => {
    setJournalEntry((prev: any) => {
      if (!prev || !prev.lines) return prev;
      const lines = [...prev.lines];
      lines.splice(index, 1);

      let totalDr = 0;
      let totalCr = 0;
      lines.forEach((l: any) => {
        totalDr += typeof l.debit === "number" ? l.debit : parseFloat(l.debit) || 0;
        totalCr += typeof l.credit === "number" ? l.credit : parseFloat(l.credit) || 0;
      });
      totalDr = Math.round(totalDr * 100) / 100;
      totalCr = Math.round(totalCr * 100) / 100;
      const diff = Math.round(Math.abs(totalDr - totalCr) * 100) / 100;
      const isBalanced = diff <= 0.05 && totalDr > 0;

      return {
        ...prev,
        lines,
        total_debit: totalDr,
        total_credit: totalCr,
        difference: diff,
        is_balanced: isBalanced,
        validation: {
          ...(prev.validation || {}),
          balanced: isBalanced,
          errors: isBalanced ? [] : [`Journal unbalanced: Debit ₹${totalDr} vs Credit ₹${totalCr}`],
        },
      };
    });
  };

  // Recalculate invoice totals and automatically reconstruct balanced journal entry
  const handleRecalculateAndBalanceJournal = () => {
    // 1. Calculate item-level totals
    let computedSubtotal = 0;
    let computedCgst = 0;
    let computedSgst = 0;
    let computedIgst = 0;
    let computedCess = 0;

    const items = formData.line_items || [];
    const updatedItems = items.map((item, idx) => {
      const qty = typeof item.quantity === "number" ? item.quantity : parseFloat(String(item.quantity || "1")) || 1;
      const price = typeof item.unit_price === "number" ? item.unit_price : parseFloat(String(item.unit_price ?? item.rate ?? "0")) || 0;
      const disc = typeof item.discount === "number" ? item.discount : parseFloat(String(item.discount || "0")) || 0;
      let taxable = typeof item.taxable_amount === "number" ? item.taxable_amount : parseFloat(String(item.taxable_amount || ""));
      if (isNaN(taxable) || taxable === 0) {
        taxable = Math.max(0, Math.round((qty * price - disc) * 100) / 100);
      }

      let cgstAmt = typeof item.cgst_amount === "number" ? item.cgst_amount : parseFloat(String(item.cgst_amount || ""));
      const cgstRate = typeof item.cgst_rate === "number" ? item.cgst_rate : parseFloat(String(item.cgst_rate || "0")) || 0;
      if (isNaN(cgstAmt) || (cgstAmt === 0 && cgstRate > 0)) {
        cgstAmt = Math.round(((taxable * cgstRate) / 100) * 100) / 100;
      }

      let sgstAmt = typeof item.sgst_amount === "number" ? item.sgst_amount : parseFloat(String(item.sgst_amount || ""));
      const sgstRate = typeof item.sgst_rate === "number" ? item.sgst_rate : parseFloat(String(item.sgst_rate || "0")) || 0;
      if (isNaN(sgstAmt) || (sgstAmt === 0 && sgstRate > 0)) {
        sgstAmt = Math.round(((taxable * sgstRate) / 100) * 100) / 100;
      }

      let igstAmt = typeof item.igst_amount === "number" ? item.igst_amount : parseFloat(String(item.igst_amount || ""));
      const igstRate = typeof item.igst_rate === "number" ? item.igst_rate : parseFloat(String(item.igst_rate || "0")) || 0;
      if (isNaN(igstAmt) || (igstAmt === 0 && igstRate > 0)) {
        igstAmt = Math.round(((taxable * igstRate) / 100) * 100) / 100;
      }

      let cessAmt = typeof item.cess_amount === "number" ? item.cess_amount : parseFloat(String(item.cess_amount || "0")) || 0;
      const itemTot = Math.round((taxable + (cgstAmt || 0) + (sgstAmt || 0) + (igstAmt || 0) + (cessAmt || 0)) * 100) / 100;

      computedSubtotal += taxable;
      computedCgst += cgstAmt || 0;
      computedSgst += sgstAmt || 0;
      computedIgst += igstAmt || 0;
      computedCess += cessAmt || 0;

      return {
        ...item,
        quantity: qty,
        unit_price: price,
        discount: disc,
        taxable_amount: taxable,
        cgst_amount: cgstAmt || null,
        sgst_amount: sgstAmt || null,
        igst_amount: igstAmt || null,
        cess_amount: cessAmt || null,
        total: itemTot,
      };
    });

    // If subtotal is still 0 from items, fallback to current entered header subtotal/total
    if (computedSubtotal === 0 && (formData.subtotal || formData.total_amount)) {
      computedSubtotal = formData.subtotal || formData.total_amount || 0;
    }
    if (computedCgst === 0 && (formData.cgst_amount || formData.cgst)) computedCgst = formData.cgst_amount || formData.cgst || 0;
    if (computedSgst === 0 && (formData.sgst_amount || formData.sgst)) computedSgst = formData.sgst_amount || formData.sgst || 0;
    if (computedIgst === 0 && (formData.igst_amount || formData.igst)) computedIgst = formData.igst_amount || formData.igst || 0;

    computedSubtotal = Math.round(computedSubtotal * 100) / 100;
    computedCgst = Math.round(computedCgst * 100) / 100;
    computedSgst = Math.round(computedSgst * 100) / 100;
    computedIgst = Math.round(computedIgst * 100) / 100;
    computedCess = Math.round(computedCess * 100) / 100;
    const computedTaxTotal = Math.round((computedCgst + computedSgst + computedIgst + computedCess) * 100) / 100;
    const computedTotalAmount = Math.round((computedSubtotal + computedTaxTotal) * 100) / 100;

    // 2. Update formData
    setFormData((prev) => ({
      ...prev,
      line_items: updatedItems.length > 0 ? updatedItems : prev.line_items,
      subtotal: computedSubtotal,
      cgst_amount: computedCgst || null,
      cgst: computedCgst || null,
      sgst_amount: computedSgst || null,
      sgst: computedSgst || null,
      igst_amount: computedIgst || null,
      igst: computedIgst || null,
      tax_total: computedTaxTotal,
      total_amount: computedTotalAmount,
    }));

    // 3. TDS Calculation
    const tdsRaw: any = accountingData.tds_assessment || accountingData.tds || {};
    const tdsApp = Boolean(tdsRaw.tds_applicable ?? tdsRaw.applicable);
    const tdsRate = parseFloat(String(tdsRaw.approved_tds_rate ?? tdsRaw.tds_rate ?? tdsRaw.rate ?? "0")) || 0;
    let tdsAmount = 0;
    if (tdsApp && tdsRate > 0) {
      tdsAmount = Math.round(((computedSubtotal * tdsRate) / 100) * 100) / 100;
    }
    const accountsPayable = Math.max(0, Math.round((computedTotalAmount - tdsAmount) * 100) / 100);

    // 4. Build Balanced Journal Lines
    const newJournalLines: any[] = [];
    if (updatedItems.length > 0) {
      updatedItems.forEach((item, idx) => {
        const acc = accountingLines[idx] || {};
        const accId = acc.approved_account_id || acc.final_account_id || acc.account_id || zohoAccounts?.[0]?.zoho_account_id || "ACC_EXPENSE";
        const accName = acc.approved_account_name || acc.final_account_name || acc.account_name || zohoAccounts?.[0]?.account_name || (item.description || `Line ${idx + 1} Expense`);
        newJournalLines.push({
          account_id: accId,
          account_name: accName,
          line_type: "EXPENSE",
          debit: item.taxable_amount || 0,
          credit: 0,
          source_line_index: idx + 1,
          description: item.description || `Line ${idx + 1} Expense`,
          provenance: "DETERMINISTIC",
        });
      });
    } else {
      const defaultId = zohoAccounts?.[0]?.zoho_account_id || "ACC_EXPENSE";
      const defaultName = zohoAccounts?.[0]?.account_name || "General Expenses";
      newJournalLines.push({
        account_id: defaultId,
        account_name: defaultName,
        line_type: "EXPENSE",
        debit: computedSubtotal,
        credit: 0,
        source_line_index: 1,
        description: "Invoice Expense",
        provenance: "DETERMINISTIC",
      });
    }

    // Input Tax Debits
    if (computedCgst > 0) {
      newJournalLines.push({
        account_id: "TAX_INPUT_CGST",
        account_name: "Input CGST",
        line_type: "INPUT_TAX",
        debit: computedCgst,
        credit: 0,
        source_line_index: null,
        description: `Input CGST (9%)`,
        provenance: "DETERMINISTIC",
      });
    }
    if (computedSgst > 0) {
      newJournalLines.push({
        account_id: "TAX_INPUT_SGST",
        account_name: "Input SGST",
        line_type: "INPUT_TAX",
        debit: computedSgst,
        credit: 0,
        source_line_index: null,
        description: `Input SGST (9%)`,
        provenance: "DETERMINISTIC",
      });
    }
    if (computedIgst > 0) {
      newJournalLines.push({
        account_id: "TAX_INPUT_IGST",
        account_name: "Input IGST",
        line_type: "INPUT_TAX",
        debit: computedIgst,
        credit: 0,
        source_line_index: null,
        description: `Input IGST`,
        provenance: "DETERMINISTIC",
      });
    }

    // TDS Payable Credit
    if (tdsAmount > 0) {
      newJournalLines.push({
        account_id: "LIAB_TDS_PAYABLE",
        account_name: `TDS Payable - ${tdsRaw.tds_section || "Statutory"}`,
        line_type: "TDS_PAYABLE",
        debit: 0,
        credit: tdsAmount,
        source_line_index: null,
        description: `TDS @ ${tdsRate}% on ₹${computedSubtotal}`,
        provenance: "DETERMINISTIC",
      });
    }

    // Accounts Payable Credit
    const vendorName = formData.vendor_name || "Vendor";
    newJournalLines.push({
      account_id: "LIAB_AP",
      account_name: `Accounts Payable - ${vendorName}`,
      line_type: "ACCOUNTS_PAYABLE",
      debit: 0,
      credit: accountsPayable,
      source_line_index: null,
      description: `Net Payable to ${vendorName}`,
      provenance: "DETERMINISTIC",
    });

    let totDr = 0;
    let totCr = 0;
    newJournalLines.forEach((l) => {
      totDr += l.debit || 0;
      totCr += l.credit || 0;
    });
    totDr = Math.round(totDr * 100) / 100;
    totCr = Math.round(totCr * 100) / 100;
    const diff = Math.round(Math.abs(totDr - totCr) * 100) / 100;
    const isBal = diff <= 0.05 && totDr > 0;

    setJournalEntry({
      status: isBal ? "BALANCED" : "REVIEW_REQUIRED",
      lines: newJournalLines,
      total_debit: totDr,
      total_credit: totCr,
      difference: diff,
      is_balanced: isBal,
      currency: "INR",
      validation: {
        balanced: isBal,
        tolerance: 0.05,
        errors: isBal ? [] : [`Debit ₹${totDr} vs Credit ₹${totCr}`],
        warnings: [],
      },
    });

    setActionNotice("✓ Invoice totals and General Ledger journal successfully recalculated and balanced!");
    setTimeout(() => setActionNotice(null), 4000);
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

  // Save changes handler (persists authoritative current VLM data and accounting classifications, triggers re-validation)
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
        accountingData,
        journalEntry
      );
      setInvoice(updated);
      if (updated.current_accounting_output) {
        setAccountingData(updated.current_accounting_output);
      }
      setGstResult(updated.gst_result || null);
      setItcResult(updated.itc_result || null);
      setFinancialValidationResult(updated.financial_validation_result || null);
      setJournalEntry(updated.journal_entry || null);
      setSaveSuccess(true);

      // Check results for descriptive feedback
      const hasErrors =
        updated.financial_validation_result?.overall_status === "MISMATCH" ||
        (updated.journal_entry &&
          !updated.journal_entry.is_balanced &&
          updated.journal_entry.difference !== 0);
      const hasWarnings =
        updated.itc_result?.status === "REVIEW_REQUIRED" ||
        updated.gst_result?.validation_status === "GST_MISMATCH" ||
        (updated.financial_validation_result?.warnings &&
          updated.financial_validation_result.warnings.length > 0);

      if (hasErrors) {
        setActionNotice("⚠ Changes saved. Please review mathematical discrepancies or unbalanced journal.");
      } else if (hasWarnings) {
        setActionNotice("⚠ Changes saved with advisory statutory warnings.");
      } else {
        setActionNotice("✓ Invoice changes saved and re-validated successfully!");
      }

      // Refresh journal preview & vendor status with saved changes
      getJournalPreview(invoiceId).then(setJournalPreview).catch(() => null);
      getInvoiceVendorStatus(invoiceId).then(setVendorStatus).catch(() => null);

      setTimeout(() => {
        setSaveSuccess(false);
        setActionNotice(null);
      }, 5000);
    } catch (err: any) {
      setError(err.message || "Failed to save changes.");
    } finally {
      setIsSaving(false);
    }
  };

  // Explicit Add Vendor to Zoho Handler
  const handleAddVendorToZoho = async () => {
    if (!invoiceId) return;
    try {
      setIsAddingVendor(true);
      setError(null);
      const res = await addVendorToZoho(invoiceId);
      setActionNotice(`✓ Vendor '${formData.vendor_name || "Vendor"}' successfully added to Zoho Books! (ID: ${res.contact_id})`);
      setVendorStatus({
        invoice_id: invoiceId,
        is_zoho_connected: true,
        match_status: "MATCHED",
        invoice_vendor: {
          vendor_name: formData.vendor_name,
          vendor_gstin: formData.vendor_gstin,
          vendor_pan: formData.vendor_pan,
          vendor_address: formData.vendor_address,
          vendor_phone: formData.vendor_phone,
          vendor_email: formData.vendor_email,
        },
        matched_vendor: {
          contact_id: res.contact_id,
          contact_name: formData.vendor_name,
          gst_no: formData.vendor_gstin,
          pan_no: formData.vendor_pan,
        },
        requires_action: false,
      });
      setVendorModalOpen(false);
      setTimeout(() => setActionNotice(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to add vendor to Zoho Books.");
    } finally {
      setIsAddingVendor(false);
    }
  };

  // Real Journal Approval Handler
  const handleApproveJournal = async () => {
    if (!invoiceId) return;
    try {
      setIsApprovingJournal(true);
      setError(null);
      const res = await approveJournal(invoiceId);
      if (res.journal_entry) {
        setJournalEntry(res.journal_entry);
      } else {
        setJournalEntry((prev) =>
          prev
            ? {
                ...prev,
                status: "APPROVED",
                approval_status: "APPROVED",
                approved_by: res.approved_by,
                approved_at: res.approved_at,
              }
            : null
        );
      }
      setInvoice((prev) =>
        prev
          ? {
              ...prev,
              journal_entry: res.journal_entry || prev.journal_entry,
            }
          : null
      );
      setActionNotice("General Ledger journal approved successfully!");
      setTimeout(() => setActionNotice(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to approve General Ledger journal");
    } finally {
      setIsApprovingJournal(false);
    }
  };

  // Real TDS Approval Handler
  const handleApproveTds = async () => {
    if (!invoiceId) return;
    try {
      setIsApprovingTds(true);
      setError(null);
      const res = await approveTds(invoiceId);
      if (res.tds) {
        setAccountingData((prev) => ({
          ...prev,
          tds: res.tds,
          tds_assessment: res.tds,
        }));
      }
      if (res.journal_entry) {
        setJournalEntry(res.journal_entry);
      }
      setActionNotice("Statutory TDS assessment approved successfully!");
      setTimeout(() => setActionNotice(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to approve TDS assessment");
    } finally {
      setIsApprovingTds(false);
    }
  };

  // Accept AI suggestions into approved fields for all lines
  const handleAcceptAllAccounts = () => {
    const updated = (accountingData.accounting || []).map((acc, idx) => {
      let resolvedId = acc.final_account_id || acc.approved_account_id || acc.account_id || acc.ai_account_id;
      let resolvedName = acc.final_account_name || acc.approved_account_name || acc.account_name || acc.ai_account_name || "General Expenses";

      if (zohoAccounts && zohoAccounts.length > 0) {
        const match = zohoAccounts.find(
          (za: any) =>
            String(za.zoho_account_id) === String(resolvedId) ||
            String(za.account_name).toLowerCase().trim() === String(resolvedName).toLowerCase().trim() ||
            String(za.account_code || "").toLowerCase().trim() === String(resolvedId || "").toLowerCase().trim()
        );
        if (match) {
          resolvedId = match.zoho_account_id;
          resolvedName = match.account_name;
        } else if (!resolvedId || String(resolvedId).startsWith("ACC_")) {
          resolvedId = zohoAccounts[0].zoho_account_id;
          resolvedName = zohoAccounts[0].account_name;
        }
      } else if (!resolvedId) {
        resolvedId = `ACC_${idx + 1}`;
      }

      return {
        ...acc,
        approved_account_id: resolvedId,
        approved_account_name: resolvedName,
        final_account_id: resolvedId,
        final_account_name: resolvedName,
      };
    });
    setAccountingData({ ...accountingData, accounting: updated });
    setActionNotice("Accepted and approved all Chart of Accounts.");
    setTimeout(() => setActionNotice(null), 3000);
  };

  // Accept a single AI suggestion
  const handleAcceptAccount = (index: number) => {
    const updated = [...(accountingData.accounting || [])];
    if (updated[index]) {
      let resolvedId = updated[index].final_account_id || updated[index].approved_account_id || updated[index].account_id || updated[index].ai_account_id;
      let resolvedName = updated[index].final_account_name || updated[index].approved_account_name || updated[index].account_name || updated[index].ai_account_name || "General Expenses";

      if (zohoAccounts && zohoAccounts.length > 0) {
        const match = zohoAccounts.find(
          (za: any) =>
            String(za.zoho_account_id) === String(resolvedId) ||
            String(za.account_name).toLowerCase().trim() === String(resolvedName).toLowerCase().trim()
        );
        if (match) {
          resolvedId = match.zoho_account_id;
          resolvedName = match.account_name;
        } else if (!resolvedId || String(resolvedId).startsWith("ACC_")) {
          resolvedId = zohoAccounts[0].zoho_account_id;
          resolvedName = zohoAccounts[0].account_name;
        }
      } else if (!resolvedId) {
        resolvedId = `ACC_${index + 1}`;
      }

      updated[index] = {
        ...updated[index],
        approved_account_id: resolvedId,
        approved_account_name: resolvedName,
        final_account_id: resolvedId,
        final_account_name: resolvedName,
      };
      setAccountingData({ ...accountingData, accounting: updated });
    }
  };

  // Execute authenticated backend invoice approval
  const executeBackendApproval = async () => {
    try {
      setIsApproving(true);
      setError(null);
      await approveInvoice(invoiceId);
      setActionNotice("Invoice approved and balanced double-entry journal created!");
      setTimeout(() => setActionNotice(null), 4000);

      const [updatedInv, updatedJournal] = await Promise.all([
        getInvoice(invoiceId),
        getJournalPreview(invoiceId).catch(() => null),
      ]);
      setInvoice(updatedInv);
      if (updatedJournal) setJournalPreview(updatedJournal);
      if (updatedInv.journal_entry) setJournalEntry(updatedInv.journal_entry);
    } catch (err: any) {
      setError(err.message || "Failed to approve invoice.");
    } finally {
      setIsApproving(false);
    }
  };

  const handleApproveHitlExtractionAction = async () => {
    try {
      setIsHitlApproving(true);
      setError(null);

      // Gate 1 Closed Period Pre-flight Check
      if (periodInfo?.is_closed_period && periodResolution === "NONE") {
        setPeriodModalOpen(true);
        setError(`This invoice document date falls in a closed accounting period (Books closed through ${periodInfo.books_closed_through_date_formatted || booksClosedDate}). Please resolve the accounting period before approving.`);
        setIsHitlApproving(false);
        return;
      }

      await approveHitlExtraction(invoiceId, formData, postingDate || null, periodResolution, periodReason || null);
      setActionNotice("Stage 1 Extraction approved! Resuming AI Accounting & TDS classification...");
      setTimeout(() => {
        router.push("/");
      }, 1500);
    } catch (err: any) {
      setError(err.message || "Failed to approve extraction");
    } finally {
      setIsHitlApproving(false);
    }
  };

  const handleApproveHitlFinalAction = async () => {
    try {
      setIsHitlApproving(true);
      setError(null);

      if (periodInfo?.is_closed_period && periodResolution === "NONE") {
        setPeriodModalOpen(true);
        setError(`This invoice posting date falls in a closed accounting period (Books closed through ${periodInfo.books_closed_through_date_formatted || booksClosedDate}). An authorized exception is required.`);
        setIsHitlApproving(false);
        return;
      }

      await approveHitlFinal(invoiceId, accountingData, journalEntry, postingDate || null, periodResolution, periodReason || null);
      setActionNotice("Stage 2 Finance review approved! Invoice status set to HITL_COMPLETED awaiting Finance approval.");
      setTimeout(() => {
        router.push("/");
      }, 1500);
    } catch (err: any) {
      setError(err.message || "Failed to approve final review");
    } finally {
      setIsHitlApproving(false);
    }
  };

  // Real Approval Action Handler with Hard Block & Non-blocking Warning validation
  const handleApprove = async () => {
    // 1. Check for Hard Blocks
    const hardBlocks: string[] = [];
    const isJournalUnbalanced =
      journalEntry &&
      (!journalEntry.is_balanced ||
        journalEntry.difference !== 0 ||
        (journalEntry.total_debit || 0) <= 0);

    if (isJournalUnbalanced) {
      hardBlocks.push(
        `General Ledger journal is unbalanced (Difference: ₹${journalEntry.difference?.toLocaleString() || "0.00"}). Debits must equal Credits before approval.`
      );
    }
    if (financialValidationResult?.overall_status === "MISMATCH") {
      hardBlocks.push("Financial validation reported mathematical discrepancies.");
    }
    if (!formData.invoice_number?.trim()) {
      hardBlocks.push("Invoice number is mandatory.");
    }

    if (hardBlocks.length > 0) {
      setError(`Cannot Approve: ${hardBlocks.join(" ")} Please correct invoice line items or totals.`);
      return;
    }

    // 2. Check for Non-blocking Warnings
    const warnings: string[] = [];
    if (itcResult?.status === "REVIEW_REQUIRED") {
      warnings.push("Input Tax Credit (ITC) status is REVIEW_REQUIRED (Advisory Section 17(5) evaluation).");
    }
    if (gstResult?.validation_status === "GST_MISMATCH") {
      warnings.push("GST structure reported an advisory discrepancy.");
    }
    if (tdsResult?.applicable && !tdsResult?.is_approved && tdsResult?.approval_status !== "APPROVED") {
      warnings.push("Statutory TDS assessment has not been explicitly confirmed.");
    }
    if (gstResult?.errors && gstResult.errors.length > 0) {
      gstResult.errors.forEach((e) => warnings.push(`GST Notice: ${e}`));
    }
    if (financialValidationResult?.warnings && financialValidationResult.warnings.length > 0) {
      financialValidationResult.warnings.forEach((w) => warnings.push(w));
    }

    if (warnings.length > 0) {
      setActiveWarnings(warnings);
      setWarningModalOpen(true);
      return;
    }

    // 3. No warnings and no hard blocks: execute directly
    await executeBackendApproval();
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

  // Real Zoho Export Action Handler (Approve & Export directly in one flow)
  const handleExport = async () => {
    // Strict Vendor match guard: Stop export if vendor is not matched in Zoho
    if (vendorStatus && vendorStatus.is_zoho_connected && vendorStatus.match_status !== "MATCHED") {
      setVendorModalOpen(true);
      setError("Vendor verification required: Please check vendor details or add the vendor to Zoho Books before exporting.");
      return;
    }

    try {
      setIsExporting(true);
      setError(null);

      // 1. If invoice is not yet marked approved, execute approval first seamlessly
      if (invoice?.approval_status !== "APPROVED") {
        try {
          await approveInvoice(invoiceId);
        } catch (appErr: any) {
          console.warn("Auto-approval on export note:", appErr);
        }
      }

      // 2. Export to Zoho Books
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
    accountingData.accounting ||
    invoice?.current_accounting_output?.accounting ||
    invoice?.accounting_output?.accounting ||
    [];

  const tdsResultRaw =
    accountingData.tds_assessment ||
    (accountingData as any).tds_final ||
    accountingData.tds ||
    invoice?.current_accounting_output?.tds_assessment ||
    (invoice?.current_accounting_output as any)?.tds_final ||
    invoice?.current_accounting_output?.tds ||
    invoice?.accounting_output?.tds_assessment ||
    (invoice?.accounting_output as any)?.tds_final ||
    invoice?.accounting_output?.tds ||
    undefined;

  const defaultTdsResult: TdsResult = {
    applicable: false,
    tds_applicable: false,
    tds_section: "194C",
    tds_provision: "Section 194C",
    nature_of_payment: "Payment to Contractors / Suppliers",
    tds_rate: 0,
    tds_base_amount: formData.subtotal || 0,
    proposed_tds_amount: 0,
    reason: "Standard contractor payment below statutory withholding threshold",
    tds_reasoning: "Standard contractor payment below statutory withholding threshold",
  };

  const tdsResult: TdsResult =
    tdsResultRaw && Object.keys(tdsResultRaw).length > 0
      ? tdsResultRaw
      : defaultTdsResult;

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
            onClick={() => router.push(mode === "customer" ? "/finance/invoices" : "/finance/invoices")}
            className="btn btn-secondary"
            style={{ padding: "6px 12px", fontSize: "13px" }}
            title="Return to Invoice Registry"
          >
            <ArrowLeft size={14} />
            <span>Invoices</span>
          </button>
          {mode === "internal" && (
            <button
              onClick={() => router.push("/finance/review")}
              className="btn btn-secondary"
              style={{ padding: "6px 10px", fontSize: "12px" }}
              title="Return to Internal Review Queue"
            >
              <span>HITL Queue</span>
            </button>
          )}
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

          {/* Original Model Extraction JSON Modal Trigger */}
          <button
            type="button"
            onClick={() => setShowRawJsonModal(true)}
            className="btn btn-secondary"
            style={{ padding: "6px 12px", fontSize: "12px" }}
            title="View original immutable model extraction JSON for audit & comparison"
          >
            <FileText size={13} />
            <span>Original Model JSON</span>
          </button>

          {/* Save Changes Button */}
          <button
            type="button"
            onClick={handleSaveChanges}
            disabled={isSaving || invoice?.approval_status === "APPROVED"}
            className="btn btn-primary"
            style={{
              padding: "6px 14px",
              fontSize: "12px",
              background: saveSuccess
                ? "#16a34a"
                : "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)",
              color: "#ffffff",
            }}
            title="Save all user edits and re-run deterministic validation engines"
          >
            {isSaving ? (
              <RefreshCw size={13} className="animate-spin" />
            ) : saveSuccess ? (
              <Check size={13} />
            ) : (
              <Save size={13} />
            )}
            <span>
              {isSaving
                ? "Saving & Re-validating..."
                : saveSuccess
                ? "Saved ✓"
                : "Save Changes"}
            </span>
          </button>

          {/* Action Buttons: Reject, Approve, Export to Zoho (Internal Finance Only) */}
          {mode === "internal" && (
            <>
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
                  isApproving ||
                  invoice?.export_status === "EXPORTED"
                }
                className="btn btn-primary"
                style={{
                  padding: "6px 14px",
                  fontSize: "12px",
                  background:
                    invoice?.export_status === "EXPORTED"
                      ? "#34c759"
                      : "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
                  color: "#ffffff",
                  cursor:
                    invoice?.export_status !== "EXPORTED"
                      ? "pointer"
                      : "default",
                }}
                title={
                  invoice?.export_status === "EXPORTED"
                    ? "Already exported to Zoho Books"
                    : "Approve and Export bill to Zoho Books"
                }
              >
                <Send size={13} />
                <span>
                  {isExporting
                    ? "Syncing to Zoho..."
                    : isApproving
                    ? "Approving & Syncing..."
                    : invoice?.export_status === "EXPORTED"
                    ? "Exported to Zoho ✓"
                    : "Export to Zoho"}
                </span>
              </button>
            </>
          )}

          {/* HITL Stage 1 Extraction Action Button */}
          {mode === "hitl_extraction" && (
            <>
              <button
                type="button"
                onClick={() => router.push("/")}
                className="btn btn-secondary"
                style={{ padding: "8px 14px", fontSize: "13px" }}
              >
                <ArrowLeft size={14} />
                <span>Back to Queue</span>
              </button>

              <button
                type="button"
                onClick={handleApproveHitlExtractionAction}
                disabled={isHitlApproving}
                className="btn btn-primary"
                style={{
                  padding: "8px 20px",
                  fontSize: "13px",
                  fontWeight: 600,
                  background: "linear-gradient(135deg, #16a34a 0%, #15803d 100%)",
                  color: "#ffffff",
                  boxShadow: "0 2px 6px rgba(22, 163, 74, 0.35)",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <CheckCircle2 size={15} />
                <span>
                  {isHitlApproving ? "Approving & Running Accounting..." : "Approve & Continue to Accounting"}
                </span>
              </button>
            </>
          )}

          {/* HITL Stage 2 Final Review Action Button */}
          {mode === "hitl_final" && (
            <>
              <button
                type="button"
                onClick={() => router.push("/")}
                className="btn btn-secondary"
                style={{ padding: "8px 14px", fontSize: "13px" }}
              >
                <ArrowLeft size={14} />
                <span>Back to Queue</span>
              </button>

              <button
                type="button"
                onClick={handleApproveHitlFinalAction}
                disabled={isHitlApproving}
                className="btn btn-primary"
                style={{
                  padding: "8px 20px",
                  fontSize: "13px",
                  fontWeight: 600,
                  background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                  color: "#ffffff",
                  boxShadow: "0 2px 6px rgba(37, 99, 235, 0.35)",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <CheckCircle2 size={15} />
                <span>
                  {isHitlApproving ? "Finalizing Review..." : "Approve & Finalize HITL Review"}
                </span>
              </button>
            </>
          )}
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
                  <object
                    data={fileUrl}
                    type="application/pdf"
                    style={{ width: "100%", height: "100%", minHeight: "800px", border: "none" }}
                  >
                    <iframe
                      src={fileUrl}
                      style={{ width: "100%", height: "100%", minHeight: "800px", border: "none" }}
                      title="Invoice PDF Preview"
                    />
                  </object>
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
              {/* Review Panel Header */}
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
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Receipt size={16} color="var(--accent)" />
                      <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                        1. Invoice Information
                      </h3>
                    </div>

                    {periodInfo?.is_closed_period && (
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                            padding: "4px 10px",
                            borderRadius: "12px",
                            fontSize: "11px",
                            fontWeight: "700",
                            background: periodResolution === "PRIOR_PERIOD_EXCEPTION" ? "#fef3c7" : periodResolution === "POST_TO_OPEN_PERIOD" ? "#dcfce7" : "#fee2e2",
                            color: periodResolution === "PRIOR_PERIOD_EXCEPTION" ? "#92400e" : periodResolution === "POST_TO_OPEN_PERIOD" ? "#166534" : "#991b1b",
                            border: `1px solid ${periodResolution === "PRIOR_PERIOD_EXCEPTION" ? "#fde68a" : periodResolution === "POST_TO_OPEN_PERIOD" ? "#bbf7d0" : "#fca5a5"}`,
                          }}
                        >
                          <AlertTriangle size={12} />
                          <span>
                            {periodResolution === "PRIOR_PERIOD_EXCEPTION"
                              ? "Prior-Period Exception Approved"
                              : periodResolution === "POST_TO_OPEN_PERIOD"
                              ? "Posting to Open Period"
                              : "Closed Period Detected"}
                          </span>
                        </span>
                        <button
                          type="button"
                          onClick={() => setPeriodModalOpen(true)}
                          className="btn btn-secondary"
                          style={{ padding: "3px 10px", fontSize: "11px", height: "auto" }}
                        >
                          {periodResolution === "NONE" ? "Resolve Period" : "Change Resolution"}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Prominent Closed Period Warning Banner */}
                  {periodInfo?.is_closed_period && (
                    <div
                      style={{
                        background: "#fffbeb",
                        border: "1px solid #fde68a",
                        borderRadius: "8px",
                        padding: "12px 16px",
                        marginBottom: "16px",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "10px",
                      }}
                    >
                      <AlertTriangle size={18} color="#d97706" style={{ marginTop: "2px", flexShrink: 0 }} />
                      <div style={{ flex: 1, fontSize: "13px", color: "#92400e" }}>
                        <div style={{ fontWeight: "700", marginBottom: "3px" }}>
                          Closed Accounting Period (Audit Lock Date: {periodInfo.books_closed_through_date_formatted || booksClosedDate})
                        </div>
                        <div>
                          The physical invoice date ({formatToIndianDate(formData.invoice_date)}) falls in a closed financial audit period.
                          {periodResolution === "POST_TO_OPEN_PERIOD" ? (
                            <span style={{ color: "#166534", fontWeight: "600", marginLeft: "4px" }}>
                              Posting to open period ({formatToIndianDate(postingDate)}).
                            </span>
                          ) : periodResolution === "PRIOR_PERIOD_EXCEPTION" ? (
                            <span style={{ color: "#92400e", fontWeight: "600", marginLeft: "4px" }}>
                              Prior-Period Exception authorized with audit reason.
                            </span>
                          ) : (
                            <span style={{ color: "#b91c1c", fontWeight: "600", marginLeft: "4px" }}>
                              Please select a period resolution before Stage 1 approval.
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

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
                      <label className="form-label">Document Date (Physical)</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.invoice_date ?? ""}
                        placeholder="DD-MM-YYYY"
                        onChange={(e) => handleFieldChange("invoice_date", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label" style={{ color: periodInfo?.is_closed_period ? "var(--accent)" : "inherit", fontWeight: periodInfo?.is_closed_period ? "700" : "normal" }}>
                        Accounting Posting Date {periodInfo?.is_closed_period ? " (GL / Zoho)" : ""}
                      </label>
                      <input
                        type="text"
                        className="form-input"
                        value={postingDate || formData.invoice_date || ""}
                        placeholder="DD-MM-YYYY or YYYY-MM-DD"
                        style={{
                          borderColor: periodInfo?.is_closed_period ? "var(--accent)" : undefined,
                          background: periodInfo?.is_closed_period ? "rgba(99, 102, 241, 0.05)" : undefined,
                        }}
                        onChange={(e) => {
                          setPostingDate(e.target.value);
                          if (periodResolution === "NONE" && periodInfo?.is_closed_period) {
                            setPeriodResolution("POST_TO_OPEN_PERIOD");
                          }
                        }}
                      />
                    </div>
                    <div>
                      <label className="form-label">Due Date</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.due_date ?? ""}
                        placeholder="DD-MM-YYYY"
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
                        placeholder="State name / code"
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
                    <div>
                      <label className="form-label">Payment Terms (Days)</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.payment_terms ?? ""}
                        placeholder="e.g. 15, 30, Net 30"
                        onChange={(e) => handleFieldChange("payment_terms", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Invoice Notes / Remarks</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.notes ?? ""}
                        placeholder="Optional remarks or notes"
                        onChange={(e) => handleFieldChange("notes", e.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {/* 2. VENDOR / BILL FROM */}
                <section id="section-vendor-details" style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Building2 size={16} color="var(--text-secondary)" />
                      <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                        2. Vendor / Bill From
                      </h3>
                    </div>

                    {vendorStatus && vendorStatus.is_zoho_connected && (
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {vendorStatus.match_status === "MATCHED" ? (
                          <div
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "5px",
                              padding: "3px 10px",
                              borderRadius: "12px",
                              fontSize: "11px",
                              fontWeight: "600",
                              background: "#dcfce7",
                              color: "#166534",
                              border: "1px solid #bbf7d0",
                            }}
                          >
                            <CheckCircle2 size={12} />
                            <span>Matched in Zoho: {vendorStatus.matched_vendor?.contact_name || formData.vendor_name}</span>
                          </div>
                        ) : (
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <div
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                                padding: "3px 10px",
                                borderRadius: "12px",
                                fontSize: "11px",
                                fontWeight: "600",
                                background: "#fef3c7",
                                color: "#92400e",
                                border: "1px solid #fde68a",
                              }}
                            >
                              <AlertTriangle size={12} />
                              <span>{vendorStatus.match_status === "MISMATCH" ? "Identity Mismatch" : "Not Found in Zoho"}</span>
                            </div>
                            {mode === "internal" && (
                              <button
                                type="button"
                                onClick={() => setVendorModalOpen(true)}
                                className="btn btn-secondary"
                                style={{ padding: "3px 10px", fontSize: "11px", height: "auto" }}
                              >
                                Verify / Add to Zoho
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )}
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
                        placeholder="15-digit GSTIN"
                        onChange={(e) => handleFieldChange("vendor_gstin", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Vendor PAN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_pan ?? ""}
                        placeholder="10-digit PAN"
                        onChange={(e) => handleFieldChange("vendor_pan", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Vendor CIN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_cin ?? ""}
                        placeholder="Corporate Identification Number"
                        onChange={(e) => handleFieldChange("vendor_cin", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Vendor Phone</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_phone ?? ""}
                        placeholder="Phone / Mobile"
                        onChange={(e) => handleFieldChange("vendor_phone", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Vendor Email</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.vendor_email ?? ""}
                        placeholder="Email address"
                        onChange={(e) => handleFieldChange("vendor_email", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Vendor Address</label>
                      <textarea
                        className="form-input"
                        rows={2}
                        value={formData.vendor_address ?? ""}
                        placeholder="Full registered address"
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
                        placeholder="Customer / Company Name"
                        onChange={(e) => handleFieldChange("customer_name", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Customer GSTIN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.customer_gstin ?? ""}
                        placeholder="15-digit GSTIN"
                        onChange={(e) => handleFieldChange("customer_gstin", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Customer PAN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.customer_pan ?? ""}
                        placeholder="10-digit PAN"
                        onChange={(e) => handleFieldChange("customer_pan", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Customer Address</label>
                      <textarea
                        className="form-input"
                        rows={2}
                        value={formData.customer_address ?? ""}
                        placeholder="Billing address"
                        onChange={(e) => handleFieldChange("customer_address", e.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {/* 4. SHIPPING DETAILS */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <Building2 size={16} color="var(--text-secondary)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      4. Shipping Details (Ship To)
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div>
                      <label className="form-label">Shipping Name / Consignee</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.shipping_name ?? ""}
                        placeholder="Consignee / Site Name"
                        onChange={(e) => handleFieldChange("shipping_name", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Shipping GSTIN</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.shipping_gstin ?? ""}
                        placeholder="Consignee GSTIN"
                        onChange={(e) => handleFieldChange("shipping_gstin", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Shipping Address</label>
                      <textarea
                        className="form-input"
                        rows={2}
                        value={formData.shipping_address ?? ""}
                        placeholder="Delivery / Warehouse / Site address"
                        onChange={(e) => handleFieldChange("shipping_address", e.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {/* 5. LINE ITEMS */}
                <section id="section-line-items" style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px", borderRadius: "8px", padding: "12px", transition: "background-color 0.5s ease" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Layers size={16} color="var(--accent)" />
                      <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                        5. Line Items
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
                      border: "1px solid #cbd5e1",
                      borderRadius: "8px",
                      background: "#ffffff",
                      boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                    }}
                  >
                    <table style={{ width: "100%", minWidth: "1550px", borderCollapse: "collapse", fontSize: "12px" }}>
                      <thead>
                        <tr style={{ background: "#f8fafc", borderBottom: "2px solid #e2e8f0", color: "#334155", textAlign: "left", fontWeight: "600" }}>
                          <th style={{ padding: "10px 8px", width: "36px", textAlign: "center" }}>#</th>
                          <th style={{ padding: "10px 8px", minWidth: "220px" }}>Description</th>
                          {mode !== "hitl_extraction" && (
                            <th style={{ padding: "10px 8px", minWidth: "210px" }}>Expense Account (COA)</th>
                          )}
                          <th style={{ padding: "10px 8px", minWidth: "90px" }}>HSN/SAC</th>
                          <th style={{ padding: "10px 8px", minWidth: "65px" }}>Qty</th>
                          <th style={{ padding: "10px 8px", minWidth: "65px" }}>Unit</th>
                          <th style={{ padding: "10px 8px", minWidth: "100px" }}>Unit Price</th>
                          <th style={{ padding: "10px 8px", minWidth: "80px" }}>Discount</th>
                          <th style={{ padding: "10px 8px", minWidth: "105px" }}>Taxable</th>
                          <th style={{ padding: "10px 8px", minWidth: "65px" }}>CGST %</th>
                          <th style={{ padding: "10px 8px", minWidth: "90px" }}>CGST Amt</th>
                          <th style={{ padding: "10px 8px", minWidth: "65px" }}>SGST %</th>
                          <th style={{ padding: "10px 8px", minWidth: "90px" }}>SGST Amt</th>
                          <th style={{ padding: "10px 8px", minWidth: "65px" }}>IGST %</th>
                          <th style={{ padding: "10px 8px", minWidth: "90px" }}>IGST Amt</th>
                          <th style={{ padding: "10px 8px", minWidth: "65px" }}>Cess %</th>
                          <th style={{ padding: "10px 8px", minWidth: "85px" }}>Cess Amt</th>
                          <th style={{ padding: "10px 8px", minWidth: "115px" }}>Total</th>
                          <th style={{ padding: "10px 8px", width: "40px" }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {formData.line_items && formData.line_items.length > 0 ? (
                          formData.line_items.map((item, idx) => {
                            const acc = accountingLines[idx] || {};
                            return (
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
                                {mode !== "hitl_extraction" && (
                                  <td style={{ padding: "6px" }}>
                                    {zohoAccounts && zohoAccounts.length > 0 ? (
                                      <div>
                                        <select
                                          className="table-input"
                                          style={{
                                            background: "#ffffff",
                                            border: "1px solid var(--border-subtle)",
                                            borderRadius: "var(--radius-sm)",
                                            padding: "4px 6px",
                                            width: "100%",
                                            fontSize: "11px",
                                            fontWeight: "500",
                                            color: "var(--text-primary)",
                                          }}
                                          value={
                                            zohoAccounts.some((za: any) => String(za.zoho_account_id) === String(acc.approved_account_id || acc.final_account_id || acc.account_id))
                                              ? String(acc.approved_account_id || acc.final_account_id || acc.account_id)
                                              : (zohoAccounts.find((za: any) => za.account_name.toLowerCase().trim() === String(acc.approved_account_name || acc.final_account_name || acc.account_name || acc.ai_account_name || "").toLowerCase().trim())?.zoho_account_id || (acc.account_id || "PROPOSED"))
                                          }
                                          onChange={(e) => {
                                            const selId = e.target.value;
                                            const match = zohoAccounts.find((za: any) => String(za.zoho_account_id) === String(selId));
                                            const selName = match ? match.account_name : selId;
                                            handleAccountingItemChange(idx, "approved_account_id", selId);
                                            handleAccountingItemChange(idx, "approved_account_name", selName);
                                            handleAccountingItemChange(idx, "final_account_id", selId);
                                            handleAccountingItemChange(idx, "final_account_name", selName);
                                            handleAccountingItemChange(idx, "account_id", selId);
                                            handleAccountingItemChange(idx, "account_name", selName);
                                            handleAccountingItemChange(idx, "line_index", idx + 1);
                                          }}
                                        >
                                          <option value="">-- Select COA Account --</option>
                                          {/* Custom AI option if not directly in zoho master list */}
                                          {(acc.approved_account_name || acc.account_name || acc.ai_account_name) && !zohoAccounts.some((za: any) => String(za.zoho_account_id) === String(acc.account_id) || za.account_name.toLowerCase().trim() === String(acc.approved_account_name || acc.account_name || acc.ai_account_name || "").toLowerCase().trim()) && (
                                            <option value={acc.account_id || "PROPOSED"}>
                                              {acc.approved_account_name || acc.account_name || acc.ai_account_name} (AI Proposed)
                                            </option>
                                          )}
                                          {zohoAccounts.map((za: any) => (
                                            <option key={za.zoho_account_id || za.id} value={za.zoho_account_id}>
                                              {za.account_name} ({za.account_type || "expense"})
                                            </option>
                                          ))}
                                        </select>
                                        {(acc.ai_account_name || acc.account_name) && (
                                          <div style={{ fontSize: "10px", color: "#2563eb", marginTop: "2px", fontWeight: 500 }}>
                                            🤖 AI: {acc.ai_account_name || acc.account_name}
                                          </div>
                                        )}
                                      </div>
                                    ) : (
                                      <div>
                                        <input
                                          type="text"
                                          className="table-input"
                                          style={{ fontSize: "11px", fontWeight: "600", color: "#1e293b" }}
                                          value={acc.approved_account_name || acc.final_account_name || acc.account_name || acc.ai_account_name || ""}
                                          placeholder="e.g. Purchase of Goods / Raw Materials"
                                          onChange={(e) => {
                                            handleAccountingItemChange(idx, "final_account_name", e.target.value);
                                            handleAccountingItemChange(idx, "approved_account_name", e.target.value);
                                            handleAccountingItemChange(idx, "account_name", e.target.value);
                                            handleAccountingItemChange(idx, "line_index", idx + 1);
                                          }}
                                        />
                                        {(acc.ai_account_name || acc.account_name) && (
                                          <div style={{ fontSize: "10px", color: "#2563eb", marginTop: "2px" }}>
                                            🤖 AI: {acc.ai_account_name || acc.account_name}
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </td>
                                )}
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
                                    type="text"
                                    className="table-input"
                                    value={item.unit ?? ""}
                                    placeholder="Nos/Kg"
                                    onChange={(e) => handleLineItemChange(idx, "unit", e.target.value)}
                                  />
                                </td>
                                <td style={{ padding: "6px" }}>
                                  <input
                                    type="number"
                                    className="table-input"
                                    value={item.unit_price ?? item.rate ?? ""}
                                    placeholder="0.00"
                                    onChange={(e) => {
                                      const val = parseFloat(e.target.value) || 0;
                                      handleLineItemChange(idx, "unit_price", val);
                                      handleLineItemChange(idx, "rate", val);
                                    }}
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
                                    value={item.cess_rate ?? ""}
                                    placeholder="0%"
                                    onChange={(e) => handleLineItemChange(idx, "cess_rate", parseFloat(e.target.value) || 0)}
                                  />
                                </td>
                                <td style={{ padding: "6px" }}>
                                  <input
                                    type="number"
                                    className="table-input"
                                    value={item.cess_amount ?? ""}
                                    placeholder="0.00"
                                    onChange={(e) => handleLineItemChange(idx, "cess_amount", parseFloat(e.target.value) || 0)}
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
                            );
                          })
                        ) : (
                          <tr>
                            <td colSpan={19} style={{ padding: "20px", textAlign: "center", color: "var(--text-secondary)" }}>
                              No line items extracted. Click "+ Add Item Row" to add.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>

                {/* 6. PAYMENT & BANK DETAILS */}
                <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <CreditCard size={16} color="var(--text-secondary)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      6. Payment & Bank Details
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div>
                      <label className="form-label">Payment Terms</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.payment_terms ?? ""}
                        placeholder="e.g. Net 30, Due on Receipt"
                        onChange={(e) => handleFieldChange("payment_terms", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">UPI ID / VPA</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.upi_id ?? ""}
                        placeholder="e.g. merchant@upi"
                        onChange={(e) => handleBankChange("upi_id", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Account Holder Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.account_holder_name ?? ""}
                        placeholder="Beneficiary / Account Name"
                        onChange={(e) => handleBankChange("account_holder_name", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Bank Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.bank_name ?? ""}
                        placeholder="Bank Name (e.g. HDFC, ICICI, SBI)"
                        onChange={(e) => handleBankChange("bank_name", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Account Number</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.account_number ?? ""}
                        placeholder="Bank Account Number"
                        onChange={(e) => handleBankChange("account_number", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">IFSC Code</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.ifsc_code ?? ""}
                        placeholder="11-character IFSC Code"
                        onChange={(e) => handleBankChange("ifsc_code", e.target.value)}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2" }}>
                      <label className="form-label">Branch & Address</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.bank_details?.branch ?? ""}
                        placeholder="Branch Name / City"
                        onChange={(e) => handleBankChange("branch", e.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {/* 7. FINANCIAL TOTALS & TAX BREAKDOWN */}
                <section id="section-financial-totals" style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px", borderRadius: "8px", padding: "12px", transition: "background-color 0.5s ease" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <FileSpreadsheet size={16} color="var(--accent)" />
                    <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                      7. Financial Totals & Tax Breakdown
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px" }}>
                    <div>
                      <label className="form-label">Subtotal (Taxable Amount)</label>
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
                      <label className="form-label">CGST Amount</label>
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
                      <label className="form-label">SGST Amount</label>
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
                      <label className="form-label">IGST Amount</label>
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
                      <label className="form-label">Cess Amount</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.cess_amount ?? formData.cess ?? ""}
                        placeholder="0.00"
                        onChange={(e) => {
                          const val = e.target.value === "" ? null : parseFloat(e.target.value);
                          handleFieldChange("cess_amount", val);
                          handleFieldChange("cess", val);
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
                    <div>
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

                {/* 8. STATUTORY TDS ASSESSMENT */}
                {mode !== "hitl_extraction" && tdsResult && (
                  <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Scale size={16} color="var(--accent)" />
                        <h3 style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                          8. Statutory TDS Assessment
                        </h3>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {(() => {
                          const isApp = tdsResult.tds_applicable ?? tdsResult.applicable;
                          if (isApp === null || isApp === undefined) {
                            return (
                              <span
                                className="badge badge-pending"
                                style={{ fontSize: "11px", backgroundColor: "#f1f5f9", color: "#475569" }}
                              >
                                TDS Status: PROPOSED
                              </span>
                            );
                          }
                          if (!isApp) {
                            return (
                              <span className="badge badge-success" style={{ fontSize: "11px" }}>
                                TDS Not Applicable ✓
                              </span>
                            );
                          }
                          const isApproved = tdsResult.is_approved || tdsResult.approval_status === "APPROVED";
                          return (
                            <>
                              <span className="badge badge-uploaded" style={{ fontSize: "11px" }}>
                                TDS Applicable
                              </span>
                              <span
                                className={`badge ${isApproved ? "badge-success" : "badge-warning"}`}
                                style={{ fontSize: "11px", fontWeight: "700" }}
                              >
                                {isApproved ? "Status: APPROVED ✓" : "Status: PENDING APPROVAL"}
                              </span>
                            </>
                          );
                        })()}
                        {mode === "internal" && ((tdsResult.tds_applicable ?? tdsResult.applicable) && !(tdsResult.is_approved || tdsResult.approval_status === "APPROVED")) && (
                          <button
                            type="button"
                            onClick={handleApproveTds}
                            disabled={isApprovingTds}
                            className="btn btn-primary"
                            style={{
                              padding: "4px 12px",
                              fontSize: "11px",
                              fontWeight: "600",
                              background: "#16a34a",
                              borderColor: "#16a34a",
                              color: "#ffffff",
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                            }}
                          >
                            {isApprovingTds ? (
                              <>
                                <div className="spinner" style={{ width: "10px", height: "10px", borderWidth: "2px" }} />
                                <span>Approving...</span>
                              </>
                            ) : (
                              <>
                                <Check size={12} />
                                <span>Approve TDS</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                        gap: "14px",
                        background: "#fafafa",
                        padding: "16px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      {/* TDS Applicable Toggle */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Applicable
                        </label>
                        <select
                          value={tdsResult.tds_applicable === false || tdsResult.applicable === false ? "false" : (tdsResult.tds_applicable || tdsResult.applicable ? "true" : "false")}
                          onChange={(e) => {
                            const isApp = e.target.value === "true";
                            setAccountingData((prev: any) => {
                              const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                              currTds.tds_applicable = isApp;
                              currTds.applicable = isApp;
                              if (!isApp) {
                                currTds.tds_rate = null;
                                currTds.proposed_tds_amount = 0.0;
                              }
                              return {
                                ...prev,
                                tds_assessment: currTds,
                                tds: currTds,
                                tds_final: currTds,
                              };
                            });
                          }}
                          style={{
                            width: "100%",
                            padding: "6px 10px",
                            fontSize: "12px",
                            fontWeight: "600",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--border-subtle)",
                            background: "#ffffff",
                          }}
                        >
                          <option value="false">No (TDS Not Applicable)</option>
                          <option value="true">Yes (TDS Applicable)</option>
                        </select>
                      </div>

                      {/* TDS Section */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Section / Provision
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. 194C, 194J, 194Q, 194I"
                          value={tdsResult.tds_section || tdsResult.tds_provision || ""}
                          onChange={(e) => {
                            const val = e.target.value;
                            setAccountingData((prev: any) => {
                              const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                              currTds.tds_section = val;
                              currTds.section = val;
                              return {
                                ...prev,
                                tds_assessment: currTds,
                                tds: currTds,
                                tds_final: currTds,
                              };
                            });
                          }}
                          style={{
                            width: "100%",
                            padding: "6px 10px",
                            fontSize: "12px",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--border-subtle)",
                            background: "#ffffff",
                          }}
                        />
                      </div>

                      {/* Nature of Payment */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          Nature of Payment
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. Professional services, Purchase of goods"
                          value={tdsResult.nature_of_payment || ""}
                          onChange={(e) => {
                            const val = e.target.value;
                            setAccountingData((prev: any) => {
                              const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                              currTds.nature_of_payment = val;
                              currTds.nature = val;
                              return {
                                ...prev,
                                tds_assessment: currTds,
                                tds: currTds,
                                tds_final: currTds,
                              };
                            });
                          }}
                          style={{
                            width: "100%",
                            padding: "6px 10px",
                            fontSize: "12px",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--border-subtle)",
                            background: "#ffffff",
                          }}
                        />
                      </div>

                      {/* TDS Rate (%) */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Rate (%)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          placeholder="e.g. 0.1, 1, 2, 10"
                          value={tdsResult.tds_rate !== null && tdsResult.tds_rate !== undefined ? tdsResult.tds_rate : ""}
                          onChange={(e) => {
                            const val = e.target.value === "" ? null : parseFloat(e.target.value);
                            setAccountingData((prev: any) => {
                              const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                              currTds.tds_rate = val;
                              currTds.rate = val;
                              const subtotal = parseFloat(String(formData.subtotal || formData.total_amount || 0));
                              if (val !== null && subtotal > 0) {
                                currTds.proposed_tds_amount = Math.round((subtotal * val) / 100 * 100) / 100;
                              }
                              return {
                                ...prev,
                                tds_assessment: currTds,
                                tds: currTds,
                                tds_final: currTds,
                              };
                            });
                          }}
                          style={{
                            width: "100%",
                            padding: "6px 10px",
                            fontSize: "12px",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--border-subtle)",
                            background: "#ffffff",
                          }}
                        />
                      </div>

                      {/* TDS Base Amount */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Base Amount (₹)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          placeholder="Subtotal"
                          value={tdsResult.tds_base_amount !== null && tdsResult.tds_base_amount !== undefined ? tdsResult.tds_base_amount : (formData.subtotal || "")}
                          onChange={(e) => {
                            const val = e.target.value === "" ? null : parseFloat(e.target.value);
                            setAccountingData((prev: any) => {
                              const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                              currTds.tds_base_amount = val;
                              currTds.base_amount = val;
                              return {
                                ...prev,
                                tds_assessment: currTds,
                                tds: currTds,
                                tds_final: currTds,
                              };
                            });
                          }}
                          style={{
                            width: "100%",
                            padding: "6px 10px",
                            fontSize: "12px",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--border-subtle)",
                            background: "#ffffff",
                          }}
                        />
                      </div>

                      {/* Proposed TDS Amount */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Withholding Amount (₹)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          placeholder="0.00"
                          value={tdsResult.proposed_tds_amount !== null && tdsResult.proposed_tds_amount !== undefined ? tdsResult.proposed_tds_amount : ""}
                          onChange={(e) => {
                            const val = e.target.value === "" ? null : parseFloat(e.target.value);
                            setAccountingData((prev: any) => {
                              const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                              currTds.proposed_tds_amount = val;
                              currTds.tds_amount = val;
                              return {
                                ...prev,
                                tds_assessment: currTds,
                                tds: currTds,
                                tds_final: currTds,
                              };
                            });
                          }}
                          style={{
                            width: "100%",
                            padding: "6px 10px",
                            fontSize: "12px",
                            fontWeight: "700",
                            color: "var(--accent)",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--border-subtle)",
                            background: "#ffffff",
                          }}
                        />
                      </div>

                      {(() => {
                        const reason = tdsResult.tds_reasoning ?? tdsResult.reason;
                        if (reason) {
                          return (
                            <div style={{ gridColumn: "1 / -1", marginTop: "4px" }}>
                              <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "2px" }}>
                                Model Reasoning & Statutory Basis
                              </div>
                              <div style={{ fontSize: "12px", color: "var(--text-primary)", background: "#f1f5f9", padding: "8px 12px", borderRadius: "var(--radius-sm)" }}>
                                {reason}
                              </div>
                            </div>
                          );
                        }
                        return null;
                      })()}
                    </div>
                  </section>
                )}

                {/* 9. GST & TAX SUMMARY */}
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
                        9. GST & Tax Summary
                      </h3>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span
                        className={`badge ${
                          (gstResult?.supply_type === "INTRA_STATE" || (!gstResult && (formData.cgst_amount || formData.cgst || formData.sgst_amount || formData.sgst)))
                            ? "badge-success"
                            : "badge-uploaded"
                        }`}
                        style={{ fontSize: "11px", fontWeight: "600" }}
                      >
                        {(gstResult?.supply_type === "INTRA_STATE" || (!gstResult && (formData.cgst_amount || formData.cgst || formData.sgst_amount || formData.sgst)))
                          ? "Intra-State (CGST + SGST)"
                          : "Inter-State (IGST)"}
                      </span>
                      {gstResult && (
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
                          {gstResult.validation_status === "PASSED" ? "GST Validated ✓" : (gstResult.validation_status || "PENDING")}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Concise GST Card */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                      gap: "12px",
                      background: "#fafafa",
                      padding: "14px 16px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-subtle)",
                      fontSize: "12px",
                    }}
                  >
                    {(gstResult?.supply_type === "INTER_STATE" || (formData.igst_amount || formData.igst)) ? (
                      <div>
                        <div style={{ color: "var(--text-secondary)", fontSize: "11px", marginBottom: "2px" }}>IGST</div>
                        <div style={{ fontWeight: "700", fontSize: "14px" }}>
                          ₹{(gstResult?.extracted?.igst_amount ?? formData.igst_amount ?? formData.igst ?? 0).toLocaleString()}
                        </div>
                      </div>
                    ) : (
                      <>
                        <div>
                          <div style={{ color: "var(--text-secondary)", fontSize: "11px", marginBottom: "2px" }}>CGST</div>
                          <div style={{ fontWeight: "700", fontSize: "14px" }}>
                            ₹{(gstResult?.extracted?.cgst_amount ?? formData.cgst_amount ?? formData.cgst ?? 0).toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: "var(--text-secondary)", fontSize: "11px", marginBottom: "2px" }}>SGST</div>
                          <div style={{ fontWeight: "700", fontSize: "14px" }}>
                            ₹{(gstResult?.extracted?.sgst_amount ?? formData.sgst_amount ?? formData.sgst ?? 0).toLocaleString()}
                          </div>
                        </div>
                      </>
                    )}

                    <div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "11px", marginBottom: "2px" }}>Total Tax</div>
                      <div style={{ fontWeight: "700", fontSize: "14px", color: "var(--accent)" }}>
                        ₹{(gstResult?.extracted?.tax_total ?? formData.tax_total ?? 0).toLocaleString()}
                      </div>
                    </div>

                    <div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "11px", marginBottom: "2px" }}>Reverse Charge (RCM)</div>
                      <div style={{ fontWeight: "600", fontSize: "13px" }}>
                        {gstResult?.is_reverse_charge ? "Yes" : "No"}
                      </div>
                    </div>
                  </div>

                  {/* GST Mismatch / Error Warning */}
                  {gstResult?.errors && gstResult.errors.length > 0 && (
                    <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "var(--radius-sm)", padding: "10px 14px", marginTop: "10px", fontSize: "12px", color: "#991b1b" }}>
                      {gstResult.errors.map((err, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: i < gstResult.errors!.length - 1 ? "4px" : "0" }}>
                          <AlertCircle size={14} /> <span>{err}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {gstResult?.warnings && gstResult.warnings.length > 0 && (
                    <div style={{ background: "#fefce8", border: "1px solid #fef08a", borderRadius: "var(--radius-sm)", padding: "10px 14px", marginTop: "10px", fontSize: "12px", color: "#854d0e" }}>
                      {gstResult.warnings.map((w, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: i < gstResult.warnings!.length - 1 ? "4px" : "0" }}>
                          <AlertCircle size={14} /> <span>{w}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                {/* 10. INPUT TAX CREDIT (ITC) */}
                {mode !== "hitl_extraction" && itcResult && (
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
                          10. Input Tax Credit (ITC)
                        </h3>
                      </div>
                      <span
                        className={`badge ${
                          itcResult.status === "ELIGIBLE"
                            ? "badge-success"
                            : itcResult.status === "INELIGIBLE"
                            ? "badge-danger"
                            : "badge-warning"
                        }`}
                        style={{ fontSize: "11px", fontWeight: "700" }}
                      >
                        {itcResult.status === "ELIGIBLE"
                          ? "✓ ELIGIBLE"
                          : itcResult.status === "INELIGIBLE"
                          ? "✗ INELIGIBLE"
                          : (itcResult.status || "REVIEW REQUIRED")}
                      </span>
                    </div>

                    {/* Concise ITC Card */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                        gap: "12px",
                        background: "#fafafa",
                        padding: "14px 16px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        fontSize: "12px",
                      }}
                    >
                      <div>
                        <div style={{ color: "var(--text-secondary)", fontSize: "11px", marginBottom: "2px" }}>ITC Status</div>
                        <div style={{ fontWeight: "700", fontSize: "13px" }}>
                          {itcResult?.status === "ELIGIBLE"
                            ? "Eligible (Full ITC)"
                            : itcResult?.status === "INELIGIBLE"
                            ? "Ineligible / Blocked"
                            : (itcResult?.status || "Standard ITC Available")}
                        </div>
                      </div>

                      <div>
                        <div style={{ color: "var(--text-secondary)", fontSize: "11px", marginBottom: "2px" }}>Applicable ITC Amount</div>
                        <div style={{ fontWeight: "700", fontSize: "14px", color: "#15803d" }}>
                          ₹{(itcResult?.net_itc_available ?? itcResult?.eligible_itc ?? itcResult?.eligible_amount ?? formData.tax_total ?? 0).toLocaleString()}
                        </div>
                      </div>

                      {itcResult?.rule_reference && (
                        <div>
                          <div style={{ color: "var(--text-secondary)", fontSize: "11px", marginBottom: "2px" }}>Statutory Provision</div>
                          <div style={{ fontWeight: "600", fontSize: "12px", color: "var(--text-primary)" }}>
                            {itcResult.rule_reference}
                          </div>
                        </div>
                      )}
                    </div>
                  </section>
                )}

                {/* 11. FINANCIAL VALIDATION */}
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
                        11. Financial Validation
                      </h3>
                    </div>
                  </div>

                  {/* Concise Status Banner */}
                  {(!financialValidationResult || financialValidationResult.overall_status === "PASSED" || (financialValidationResult.errors?.length === 0 && !financialValidationResult.differences?.total_amount)) ? (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        background: "#f0fdf4",
                        border: "1px solid #bbf7d0",
                        borderRadius: "var(--radius-sm)",
                        padding: "12px 16px",
                        fontSize: "13px",
                        color: "#166534",
                        fontWeight: "600",
                      }}
                    >
                      <Check size={18} color="#16a34a" />
                      <span>✓ Ready for Approval — All mathematical calculations, tax subtotals, and invoice totals reconciled.</span>
                    </div>
                  ) : (
                    <div
                      style={{
                        background: "#fef2f2",
                        border: "1px solid #fca5a5",
                        borderRadius: "var(--radius-sm)",
                        padding: "12px 16px",
                        fontSize: "12px",
                        color: "#991b1b",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "700", fontSize: "13px", marginBottom: "6px" }}>
                        <AlertCircle size={16} color="#dc2626" />
                        <span>⚠ Review Required — Mathematical Discrepancy Detected</span>
                      </div>
                      {financialValidationResult.errors && financialValidationResult.errors.length > 0 ? (
                        <div style={{ marginLeft: "24px" }}>
                          {financialValidationResult.errors.map((err, i) => (
                            <div key={i} style={{ marginBottom: "3px" }}>• {err}</div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ marginLeft: "24px" }}>
                          Subtotal + Taxes does not match Grand Total. Please adjust line items or charges before approving.
                        </div>
                      )}
                    </div>
                  )}
                </section>

                {/* 12. GENERAL LEDGER JOURNAL PREVIEW */}
                {mode !== "hitl_extraction" && journalEntry && (
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
                        flexWrap: "wrap",
                        gap: "8px",
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
                          12. General Ledger Journal Preview
                        </h3>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                        {/* Status Badge */}
                        <span
                          className={`badge ${
                            (journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0))
                              ? "badge-success"
                              : "badge-danger"
                          }`}
                          style={{ fontSize: "11px", fontWeight: "700" }}
                        >
                          {(journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0))
                            ? "Status: BALANCED ✓"
                            : "Status: NOT BALANCED"}
                        </span>

                        {/* Approval Badge */}
                        <span
                          className={`badge ${
                            journalEntry.status === "APPROVED" || journalEntry.approval_status === "APPROVED"
                              ? "badge-success"
                              : (journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0))
                              ? "badge-warning"
                              : "badge-danger"
                          }`}
                          style={{ fontSize: "11px", fontWeight: "700" }}
                        >
                          {journalEntry.status === "APPROVED" || journalEntry.approval_status === "APPROVED"
                            ? "Approval: APPROVED ✓"
                            : (journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0))
                            ? "Approval: PENDING"
                            : "❌ Journal cannot be approved"}
                        </span>
                      </div>
                    </div>

                    {/* Journal Status & Approval Action Callout */}
                    <div
                      style={{
                        background:
                          journalEntry.status === "APPROVED" || journalEntry.approval_status === "APPROVED"
                            ? "#f0fdf4"
                            : !(journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0))
                            ? "#fef2f2"
                            : "#fefce8",
                        border:
                          journalEntry.status === "APPROVED" || journalEntry.approval_status === "APPROVED"
                            ? "1px solid #bbf7d0"
                            : !(journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0))
                            ? "1px solid #fecaca"
                            : "1px solid #fde68a",
                        borderRadius: "var(--radius-sm)",
                        padding: "12px 16px",
                        marginBottom: "14px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        flexWrap: "wrap",
                        gap: "10px",
                      }}
                    >
                      <div>
                        {journalEntry.status === "APPROVED" || journalEntry.approval_status === "APPROVED" ? (
                          <div>
                            <div style={{ fontWeight: "700", color: "#166534", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                              <CheckCircle2 size={15} /> General Ledger Journal Approved
                            </div>
                            <div style={{ fontSize: "11px", color: "#15803d", marginTop: "2px" }}>
                              Balanced double-entry journal is approved and authorized for Invoice Approval &amp; Zoho Books Export.
                              {journalEntry.approved_by && ` • Approved by ${journalEntry.approved_by}`}
                            </div>
                          </div>
                        ) : !(journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0)) ? (
                          <div>
                            <div style={{ fontWeight: "700", color: "#991b1b", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                              <AlertCircle size={15} /> Journal Not Balanced — Cannot Be Approved
                            </div>
                            <div style={{ fontSize: "11px", color: "#b91c1c", marginTop: "2px" }}>
                              Debits (₹{journalEntry.total_debit?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}) do not equal Credits (₹{journalEntry.total_credit?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}). Difference: ₹{journalEntry.difference?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}. Please correct invoice line items or financial totals.
                            </div>
                          </div>
                        ) : (
                          <div>
                            <div style={{ fontWeight: "700", color: "#854d0e", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                              <Clock size={15} /> Balanced Journal Pending Finance Approval
                            </div>
                            <div style={{ fontSize: "11px", color: "#a16207", marginTop: "2px" }}>
                              Total Debits equal Total Credits (₹{journalEntry.total_debit?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}). Review and approve the General Ledger journal to authorize export.
                            </div>
                          </div>
                        )}
                      </div>

                      <div>
                        {!(journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0)) ? (
                          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                            <button
                              type="button"
                              onClick={handleRecalculateAndBalanceJournal}
                              className="btn btn-primary"
                              style={{
                                padding: "7px 16px",
                                fontSize: "12px",
                                background: "#2563eb",
                                borderColor: "#2563eb",
                                color: "#fff",
                                fontWeight: "600",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                                boxShadow: "0 2px 4px rgba(37, 99, 235, 0.2)",
                                cursor: "pointer",
                              }}
                            >
                              <RefreshCw size={13} />
                              <span>Fix & Recalculate Journal</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                const el = document.getElementById("section-line-items") || document.getElementById("section-financial-totals");
                                if (el) {
                                  el.scrollIntoView({ behavior: "smooth", block: "center" });
                                  el.style.backgroundColor = "#fef3c7";
                                  setTimeout(() => {
                                    el.style.backgroundColor = "";
                                  }, 2000);
                                } else {
                                  window.scrollTo({ top: 300, behavior: "smooth" });
                                }
                              }}
                              className="btn btn-secondary"
                              style={{ padding: "6px 12px", fontSize: "12px", background: "#fff", borderColor: "#cbd5e1", color: "#475569", fontWeight: "500", cursor: "pointer" }}
                            >
                              Edit Line Items
                            </button>
                          </div>
                        ) : journalEntry.status !== "APPROVED" && journalEntry.approval_status !== "APPROVED" ? (
                          mode === "internal" ? (
                            <button
                              type="button"
                              onClick={handleApproveJournal}
                              disabled={isApprovingJournal}
                              className="btn btn-primary"
                              style={{
                                padding: "7px 18px",
                                fontSize: "12px",
                                fontWeight: "600",
                                background: "#16a34a",
                                borderColor: "#16a34a",
                                color: "#ffffff",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                                boxShadow: "0 2px 4px rgba(22, 163, 74, 0.2)",
                              }}
                            >
                              {isApprovingJournal ? (
                                <>
                                  <div className="spinner" style={{ width: "12px", height: "12px", borderWidth: "2px" }} />
                                  <span>Approving Journal...</span>
                                </>
                              ) : (
                                <>
                                  <Check size={14} />
                                  <span>Approve Journal</span>
                                </>
                              )}
                            </button>
                          ) : (
                            <span style={{ fontSize: "12px", fontWeight: "600", color: "#854d0e", display: "flex", alignItems: "center", gap: "4px" }}>
                              <Clock size={14} /> Balanced Journal
                            </span>
                          )
                        ) : (
                          <span style={{ fontSize: "12px", fontWeight: "600", color: "#166534", display: "flex", alignItems: "center", gap: "4px" }}>
                            <CheckCircle2 size={14} /> Approved ✓
                          </span>
                        )}
                      </div>
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

                    {/* Journal Lines Table (Editable Journal) */}
                    <div style={{ overflowX: "auto", marginBottom: "12px" }}>
                      <table style={{ width: "100%", fontSize: "11px", borderCollapse: "collapse", textAlign: "left" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", background: "var(--bg-main)" }}>
                            <th style={{ padding: "8px 6px", width: "30px" }}>#</th>
                            <th style={{ padding: "8px 6px", minWidth: "160px" }}>Account Name / COA</th>
                            <th style={{ padding: "8px 6px", width: "100px" }}>Account Code</th>
                            <th style={{ padding: "8px 6px", width: "110px" }}>Type</th>
                            <th style={{ padding: "8px 6px", width: "100px", textAlign: "right" }}>Debit (₹)</th>
                            <th style={{ padding: "8px 6px", width: "100px", textAlign: "right" }}>Credit (₹)</th>
                            <th style={{ padding: "8px 6px", width: "95px" }}>Provenance</th>
                            <th style={{ padding: "8px 6px", minWidth: "140px" }}>Description</th>
                            <th style={{ padding: "8px 6px", width: "36px" }}></th>
                          </tr>
                        </thead>
                        <tbody>
                          {journalEntry.lines?.map((line, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                              <td style={{ padding: "6px", color: "var(--text-secondary)" }}>{idx + 1}</td>
                              <td style={{ padding: "6px" }}>
                                {zohoAccounts && zohoAccounts.length > 0 ? (
                                  <select
                                    className="table-input"
                                    style={{
                                      background: "#ffffff",
                                      border: "1px solid var(--border-subtle)",
                                      borderRadius: "var(--radius-sm)",
                                      padding: "4px 6px",
                                      width: "100%",
                                      fontSize: "11px",
                                      fontWeight: "500",
                                      color: "var(--text-primary)",
                                    }}
                                    value={
                                      zohoAccounts.some((za: any) => String(za.zoho_account_id) === String(line.account_id))
                                        ? String(line.account_id)
                                        : (zohoAccounts.find((za: any) => za.account_name.toLowerCase().trim() === String(line.account_name || "").toLowerCase().trim())?.zoho_account_id || "")
                                    }
                                    onChange={(e) => {
                                      const selId = e.target.value;
                                      const match = zohoAccounts.find((za: any) => String(za.zoho_account_id) === String(selId));
                                      const selName = match ? match.account_name : selId;
                                      handleJournalLineChange(idx, "account_id", selId);
                                      handleJournalLineChange(idx, "account_name", selName);
                                    }}
                                  >
                                    <option value="">-- Select Account --</option>
                                    {zohoAccounts.map((za: any) => (
                                      <option key={za.zoho_account_id || za.id} value={za.zoho_account_id}>
                                        {za.account_name} ({za.account_type || "account"})
                                      </option>
                                    ))}
                                  </select>
                                ) : (
                                  <input
                                    type="text"
                                    className="table-input"
                                    style={{ fontSize: "11px", fontWeight: "600" }}
                                    value={line.account_name ?? ""}
                                    placeholder="Account Name"
                                    onChange={(e) => handleJournalLineChange(idx, "account_name", e.target.value)}
                                  />
                                )}
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="text"
                                  className="table-input"
                                  style={{ fontSize: "11px", fontFamily: "monospace", color: "var(--accent)" }}
                                  value={line.account_id ?? ""}
                                  placeholder="Code"
                                  onChange={(e) => handleJournalLineChange(idx, "account_id", e.target.value)}
                                />
                              </td>
                              <td style={{ padding: "6px" }}>
                                <select
                                  className="table-input"
                                  style={{ fontSize: "10px", padding: "4px 6px" }}
                                  value={line.line_type || "EXPENSE"}
                                  onChange={(e) => handleJournalLineChange(idx, "line_type", e.target.value)}
                                >
                                  <option value="EXPENSE">EXPENSE</option>
                                  <option value="INPUT_TAX">INPUT_TAX</option>
                                  <option value="ACCOUNTS_PAYABLE">ACCOUNTS_PAYABLE</option>
                                  <option value="TDS_PAYABLE">TDS_PAYABLE</option>
                                  <option value="ASSET">ASSET</option>
                                  <option value="ROUND_OFF">ROUND_OFF</option>
                                </select>
                              </td>
                              <td style={{ padding: "6px", textAlign: "right" }}>
                                <input
                                  type="number"
                                  step="0.01"
                                  className="table-input"
                                  style={{ textAlign: "right", fontFamily: "monospace", fontWeight: line.debit > 0 ? "700" : "normal" }}
                                  value={line.debit !== null && line.debit !== undefined ? line.debit : ""}
                                  placeholder="0.00"
                                  onChange={(e) => {
                                    const val = e.target.value === "" ? 0 : parseFloat(e.target.value) || 0;
                                    handleJournalLineChange(idx, "debit", val);
                                  }}
                                />
                              </td>
                              <td style={{ padding: "6px", textAlign: "right" }}>
                                <input
                                  type="number"
                                  step="0.01"
                                  className="table-input"
                                  style={{ textAlign: "right", fontFamily: "monospace", fontWeight: line.credit > 0 ? "700" : "normal" }}
                                  value={line.credit !== null && line.credit !== undefined ? line.credit : ""}
                                  placeholder="0.00"
                                  onChange={(e) => {
                                    const val = e.target.value === "" ? 0 : parseFloat(e.target.value) || 0;
                                    handleJournalLineChange(idx, "credit", val);
                                  }}
                                />
                              </td>
                              <td style={{ padding: "6px", fontSize: "10px", color: "var(--text-secondary)" }}>
                                <span
                                  style={{
                                    fontFamily: "monospace",
                                    padding: "2px 5px",
                                    borderRadius: "4px",
                                    background: line.provenance === "HITL_OVERRIDE" || line.provenance === "CUSTOMER_EDIT" ? "#fef3c7" : "#f1f5f9",
                                    color: line.provenance === "HITL_OVERRIDE" || line.provenance === "CUSTOMER_EDIT" ? "#92400e" : "var(--text-secondary)",
                                    fontWeight: "600",
                                    fontSize: "9px",
                                  }}
                                >
                                  {line.provenance || (mode === "customer" ? "CUSTOMER_EDIT" : "HITL_OVERRIDE")}
                                </span>
                              </td>
                              <td style={{ padding: "6px" }}>
                                <input
                                  type="text"
                                  className="table-input"
                                  style={{ fontSize: "11px" }}
                                  value={line.description ?? ""}
                                  placeholder="Description / Narration"
                                  onChange={(e) => handleJournalLineChange(idx, "description", e.target.value)}
                                />
                              </td>
                              <td style={{ padding: "6px", textAlign: "center" }}>
                                <button
                                  type="button"
                                  onClick={() => removeJournalLine(idx)}
                                  style={{ background: "none", border: "none", color: "var(--text-tertiary)", cursor: "pointer", padding: "4px" }}
                                  title="Remove journal line"
                                >
                                  <Trash2 size={13} />
                                </button>
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
                            <td colSpan={3} style={{ padding: "8px", fontSize: "10px", color: "var(--text-secondary)" }}>
                              {journalEntry.validation?.balanced ? "✓ Reconciled & Balanced" : "⚠ Review Discrepancy"}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: "12px" }}>
                      <button
                        type="button"
                        onClick={addJournalLine}
                        className="btn btn-secondary"
                        style={{ padding: "5px 12px", fontSize: "11px", display: "flex", alignItems: "center", gap: "5px" }}
                      >
                        <Plus size={12} />
                        <span>Add Journal Line</span>
                      </button>
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

                {/* 12. SAVE CHANGES & APPROVE / SYNC TO ZOHO BUTTONS */}
                <section
                  style={{
                    borderTop: "1px solid var(--border-subtle)",
                    paddingTop: "20px",
                    paddingBottom: "10px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: "12px",
                  }}
                >
                  <div style={{ flex: 1, minWidth: "240px" }}>
                    {saveSuccess && (
                      <span style={{ color: "var(--success)", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <CheckCircle2 size={16} /> Changes saved to database!
                      </span>
                    )}
                    {actionNotice && (
                      <span style={{ color: "var(--success)", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <CheckCircle2 size={16} /> {actionNotice}
                      </span>
                    )}
                    {error && (
                      <span style={{ color: "var(--danger)", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <AlertCircle size={16} /> {error}
                      </span>
                    )}
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <button
                      type="button"
                      onClick={handleSaveChanges}
                      disabled={isSaving}
                      className="btn btn-secondary"
                      style={{ padding: "10px 18px", fontSize: "13px" }}
                    >
                      <Save size={15} />
                      <span>{isSaving ? "Saving..." : "Save Changes"}</span>
                    </button>

                    {mode === "internal" && (
                      <>
                        <button
                          type="button"
                          onClick={handleApprove}
                          disabled={isApproving || invoice?.approval_status === "APPROVED"}
                          className="btn btn-primary"
                          style={{
                            padding: "10px 20px",
                            fontSize: "13px",
                            background:
                              invoice?.approval_status === "APPROVED"
                                ? "#34c759"
                                : "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)",
                            color: "#ffffff",
                          }}
                        >
                          <Check size={15} />
                          <span>
                            {isApproving
                              ? "Approving..."
                              : invoice?.approval_status === "APPROVED"
                              ? "Approved ✓"
                              : "Approve"}
                          </span>
                        </button>

                        <button
                          type="button"
                          onClick={handleExport}
                          disabled={isExporting || invoice?.export_status === "EXPORTED"}
                          className="btn btn-primary"
                          style={{
                            padding: "10px 22px",
                            fontSize: "13px",
                            fontWeight: "600",
                            background:
                              invoice?.export_status === "EXPORTED"
                                ? "#16a34a"
                                : "linear-gradient(135deg, #059669 0%, #047857 100%)",
                            color: "#ffffff",
                            boxShadow: "0 2px 6px rgba(5, 150, 105, 0.3)",
                          }}
                        >
                          <Send size={15} />
                          <span>
                            {isExporting
                              ? "Syncing to Zoho..."
                              : invoice?.export_status === "EXPORTED"
                              ? "Synced to Zoho Books ✓"
                              : "Approve & Sync to Zoho"}
                          </span>
                        </button>
                      </>
                    )}
                  </div>
                </section>
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

      {/* Raw Model Extraction JSON Modal (Audit & Comparison) */}
      {showRawJsonModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
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
              maxWidth: "800px",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              padding: "24px",
              borderRadius: "var(--radius-md)",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.2)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "700" }}>
                  Original Model Extraction JSON (Raw VLM Snapshot)
                </h3>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                  Immutable OCR &amp; VLM model output preserved for audit, comparison, and provenance verification.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowRawJsonModal(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)" }}
              >
                <X size={18} />
              </button>
            </div>

            <div
              style={{
                flex: 1,
                overflowY: "auto",
                background: "#0f172a",
                color: "#e2e8f0",
                padding: "16px",
                borderRadius: "var(--radius-sm)",
                fontFamily: "monospace",
                fontSize: "12px",
                lineHeight: "1.5",
                whiteSpace: "pre-wrap",
                marginBottom: "16px",
              }}
            >
              {JSON.stringify(invoice?.raw_vlm_output || {}, null, 2)}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(invoice?.raw_vlm_output || {}, null, 2));
                  setCopiedJson(true);
                  setTimeout(() => setCopiedJson(false), 2000);
                }}
                className="btn btn-secondary"
                style={{ padding: "6px 14px", fontSize: "12px" }}
              >
                {copiedJson ? <Check size={14} color="var(--success)" /> : <FileSpreadsheet size={14} />}
                <span>{copiedJson ? "Copied JSON!" : "Copy Raw JSON"}</span>
              </button>

              <button
                type="button"
                onClick={() => setShowRawJsonModal(false)}
                className="btn btn-primary"
                style={{ padding: "6px 16px", fontSize: "12px" }}
              >
                Close
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
          padding: 6px 8px;
          font-size: 12px;
          font-weight: 500;
          background: #ffffff;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          color: #0f172a;
          outline: none;
          height: 32px;
          transition: border-color 0.15s, box-shadow 0.15s;
        }

        .table-input:hover {
          border-color: #94a3b8;
        }

        .table-input:focus {
          border-color: #2563eb;
          box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
          background: #ffffff;
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

      {/* Warning Acknowledgement Modal */}
      {warningModalOpen && (
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
              maxWidth: "540px",
              padding: "24px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.15)",
              background: "#ffffff",
              borderRadius: "var(--radius-md)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
              <div
                style={{
                  background: "#fef3c7",
                  color: "#d97706",
                  padding: "8px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "700", margin: 0, color: "#92400e" }}>
                  Acknowledge Advisory Notices
                </h3>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: "2px 0 0" }}>
                  Some non-blocking warnings are present. Please review before approving.
                </p>
              </div>
            </div>

            <div
              style={{
                background: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: "var(--radius-sm)",
                padding: "12px 14px",
                maxHeight: "220px",
                overflowY: "auto",
                marginBottom: "20px",
              }}
            >
              {activeWarnings.map((warning, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "8px",
                    fontSize: "12px",
                    color: "#92400e",
                    marginBottom: idx < activeWarnings.length - 1 ? "8px" : "0",
                  }}
                >
                  <span style={{ fontWeight: "700", marginTop: "1px" }}>•</span>
                  <span>{warning}</span>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setWarningModalOpen(false)}
                className="btn btn-secondary"
                disabled={isApproving}
                style={{ padding: "8px 16px", fontSize: "13px" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  setWarningModalOpen(false);
                  await executeBackendApproval();
                }}
                disabled={isApproving}
                className="btn btn-primary"
                style={{
                  padding: "8px 18px",
                  fontSize: "13px",
                  background: "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)",
                  color: "#ffffff",
                }}
              >
                {isApproving ? "Approving..." : "Approve Anyway"}
              </button>
            </div>
          </div>
        </div>
      )}

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

      {/* Vendor Verification Modal */}
      {vendorModalOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
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
              maxWidth: "540px",
              padding: "24px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
              background: "#ffffff",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
              <div
                style={{
                  background: "#fef3c7",
                  color: "#d97706",
                  padding: "8px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Building2 size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "700", margin: 0, color: "#92400e" }}>
                  Vendor Not Found / Vendor Details Need Verification
                </h3>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: "2px 0 0" }}>
                  This vendor was not confidently matched in your connected Zoho Books organization.
                </p>
              </div>
            </div>

            <div
              style={{
                background: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderRadius: "var(--radius-sm)",
                padding: "14px",
                marginBottom: "16px",
                fontSize: "13px",
              }}
            >
              <div style={{ fontWeight: "700", color: "#1e293b", marginBottom: "8px", textTransform: "uppercase", fontSize: "11px", letterSpacing: "0.05em" }}>
                Invoice Vendor Details (Authoritative Saved Data):
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "6px", color: "#334155" }}>
                <span style={{ color: "#64748b" }}>Vendor Name:</span>
                <span style={{ fontWeight: "600" }}>{formData.vendor_name || "Not provided"}</span>

                <span style={{ color: "#64748b" }}>GSTIN:</span>
                <span style={{ fontWeight: "600" }}>{formData.vendor_gstin || "Not provided"}</span>

                <span style={{ color: "#64748b" }}>PAN:</span>
                <span>{formData.vendor_pan || "Not provided"}</span>

                <span style={{ color: "#64748b" }}>Address:</span>
                <span>{formData.vendor_address || "Not provided"}</span>

                {formData.vendor_email && (
                  <>
                    <span style={{ color: "#64748b" }}>Email:</span>
                    <span>{formData.vendor_email}</span>
                  </>
                )}
              </div>
            </div>

            {vendorStatus?.match_status === "MISMATCH" && vendorStatus?.matched_vendor && (
              <div
                style={{
                  background: "#fff1f2",
                  border: "1px solid #fecdd3",
                  borderRadius: "var(--radius-sm)",
                  padding: "12px 14px",
                  marginBottom: "16px",
                  fontSize: "12px",
                  color: "#9f1239",
                }}
              >
                <div style={{ fontWeight: "700", marginBottom: "4px" }}>Possible Mismatched Zoho Vendor:</div>
                <div>{vendorStatus.matched_vendor.contact_name} (GSTIN: {vendorStatus.matched_vendor.gst_no || "None"})</div>
              </div>
            )}

            {error && (
              <div
                style={{
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  borderRadius: "var(--radius-sm)",
                  padding: "10px 12px",
                  marginBottom: "16px",
                  fontSize: "12px",
                  color: "#dc2626",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "8px",
                }}
              >
                <AlertCircle size={16} style={{ flexShrink: 0, marginTop: "1px" }} />
                <span>{error}</span>
              </div>
            )}

            <p style={{ fontSize: "12px", color: "#475569", marginBottom: "20px", lineHeight: "1.5" }}>
              To ensure statutory GST compliance and prevent exporting under an unrelated vendor, please either verify/edit the vendor details or add this vendor directly into Zoho Books.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => {
                  setVendorModalOpen(false);
                  const el = document.getElementById("section-vendor-details");
                  if (el) el.scrollIntoView({ behavior: "smooth" });
                }}
                className="btn btn-secondary"
                disabled={isAddingVendor}
                style={{ padding: "8px 16px", fontSize: "13px" }}
              >
                Check Vendor Details
              </button>
              <button
                type="button"
                onClick={handleAddVendorToZoho}
                disabled={isAddingVendor || !formData.vendor_name?.trim()}
                className="btn btn-primary"
                style={{
                  padding: "8px 18px",
                  fontSize: "13px",
                  background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
                  color: "#ffffff",
                }}
              >
                {isAddingVendor ? "Adding to Zoho..." : "Add Vendor to Zoho"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
