"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getInvoice,
  getInvoiceFileUrl,
  fetchAuthenticatedFileBlobUrl,
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
  Calendar,
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
  // If ISO YYYY-MM-DD
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[3]}/${m[2]}/${m[1]}`;
  return s;
}

// Helper to derive Accounting Period month and financial year status from invoice date
function getAccountingPeriodInfo(
  dateVal: any,
  storedCategory?: string | null
): { monthYear: string; fyStatus: string; isPreviousFy: boolean } | null {
  if (!dateVal || typeof dateVal !== "string") return null;
  const s = dateVal.trim();
  if (!s || s.toLowerCase() === "none" || s.toLowerCase() === "null") return null;

  let invYear: number | null = null;
  let invMonth: number | null = null;

  // 1. ISO format: YYYY-MM-DD or YYYY/MM/DD
  const iso = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
  if (iso) {
    invYear = parseInt(iso[1], 10);
    invMonth = parseInt(iso[2], 10);
  }

  // 2. Indian format: DD-MM-YYYY or DD/MM/YYYY
  if (!invYear) {
    const dmy = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    if (dmy) {
      invMonth = parseInt(dmy[2], 10);
      invYear = parseInt(dmy[3], 10);
    }
  }

  // 3. Word month format: e.g. 31-Jul-2026, 31-Jul-26, July 31 2026
  if (!invYear) {
    const monthNames: Record<string, number> = {
      jan: 1, january: 1, feb: 2, february: 2, mar: 3, march: 3,
      apr: 4, april: 4, may: 5, jun: 6, june: 6, jul: 7, july: 7,
      aug: 8, august: 8, sep: 9, sept: 9, september: 9,
      oct: 10, october: 10, nov: 11, november: 11, dec: 12, december: 12,
    };
    const wordMatch = s.match(/([a-zA-Z]+)/);
    if (wordMatch) {
      const mStr = wordMatch[1].toLowerCase();
      if (monthNames[mStr]) {
        invMonth = monthNames[mStr];
        const yrMatch = s.match(/\b(20\d{2}|\d{2})\b/);
        if (yrMatch) {
          invYear = yrMatch[1].length === 2 ? 2000 + parseInt(yrMatch[1], 10) : parseInt(yrMatch[1], 10);
        }
      }
    }
  }

  if (!invYear || !invMonth || invMonth < 1 || invMonth > 12) return null;

  const monthNamesList = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  const monthYear = `${monthNamesList[invMonth - 1]} ${invYear}`;

  // Indian Financial Year: April 1 -> March 31
  const invFyStart = invMonth >= 4 ? invYear : invYear - 1;
  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();
  const currentFyStart = currentMonth >= 4 ? currentYear : currentYear - 1;

  const isPreviousFy = storedCategory
    ? storedCategory === "PREVIOUS_FINANCIAL_YEAR"
    : invFyStart < currentFyStart;

  const fyStatus = isPreviousFy ? "Previous Financial Year" : "Current Financial Year";

  return { monthYear, fyStatus, isPreviousFy };
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

// Helper to derive Place of Supply based on Indian state codes from GSTINs
function derivePlaceOfSupply(vendorGstin?: string | null, customerGstin?: string | null): string | null {
  const g = vendorGstin || customerGstin;
  if (!g || g.length < 2) return null;
  const code = g.substring(0, 2);
  const stateMap: Record<string, string> = {
    "01": "01-Jammu & Kashmir", "02": "02-Himachal Pradesh", "03": "03-Punjab", "04": "04-Chandigarh",
    "05": "05-Uttarakhand", "06": "06-Haryana", "07": "07-Delhi", "08": "08-Rajasthan", "09": "09-Uttar Pradesh",
    "10": "10-Bihar", "11": "11-Sikkim", "12": "12-Arunachal Pradesh", "13": "13-Nagaland", "14": "14-Manipur",
    "15": "15-Mizoram", "16": "16-Tripura", "17": "17-Meghalaya", "18": "18-Assam", "19": "19-West Bengal",
    "20": "20-Jharkhand", "21": "21-Odisha", "22": "22-Chhattisgarh", "23": "23-Madhya Pradesh", "24": "24-Gujarat",
    "26": "26-Dadra & Nagar Haveli", "27": "27-Maharashtra", "28": "28-Andhra Pradesh", "29": "29-Karnataka",
    "30": "30-Goa", "31": "31-Lakshadweep", "32": "32-Kerala", "33": "33-Tamil Nadu", "34": "34-Puducherry",
    "35": "35-Andaman & Nicobar Islands", "36": "36-Telangana", "37": "37-Andhra Pradesh (New)", "38": "38-Ladakh"
  };
  return stateMap[code] || null;
}

interface InvoiceWorkspaceProps {
  mode?: "internal" | "customer";
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
  const [lineItemErrors, setLineItemErrors] = useState<{ [key: number]: string }>({});

  // Helper to route field & line item errors directly to the target input field instead of displaying top banner
  const handleFieldErrorOrExportError = (errMsg: string) => {
    if (!errMsg) return false;
    const lineItemMatch = errMsg.match(/Line item (\d+)/i);
    if (lineItemMatch && lineItemMatch[1]) {
      const lineNum = parseInt(lineItemMatch[1], 10);
      const lineIdx = lineNum - 1;
      const cleanMsg = errMsg.replace(/^Export failed:\s*(Zoho export failed:\s*)?/i, "");
      setLineItemErrors((prev) => ({
        ...prev,
        [lineIdx]: cleanMsg,
      }));
      setError(null);
      setActionNotice(null);
      setTimeout(() => {
        const el = document.getElementById(`line-item-row-${lineIdx}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 100);
      return true;
    }
    return false;
  };

  // Editable form state
  const [formData, setFormData] = useState<ExtractedInvoiceData>({});
  const [accountingData, setAccountingData] = useState<AccountingOutput>({});
  const [gstResult, setGstResult] = useState<GstResult | null>(null);
  const [itcResult, setItcResult] = useState<ItcResult | null>(null);
  const [financialValidationResult, setFinancialValidationResult] = useState<FinancialValidationResult | null>(null);
  const [journalEntry, setJournalEntry] = useState<JournalEntry | null>(null);
  const [additionalFieldsText, setAdditionalFieldsText] = useState<string>("");
  const [zohoAccounts, setZohoAccounts] = useState<any[]>([]);
  const [coaMatchResult, setCoaMatchResult] = useState<any | null>(null);
  const [showCreateCoaModal, setShowCreateCoaModal] = useState<boolean>(false);
  const [showReviewCoaModal, setShowReviewCoaModal] = useState<boolean>(false);
  const [reviewCoaModalLineIdx, setReviewCoaModalLineIdx] = useState<number | null>(null);
  const [modalSelectedAccountId, setModalSelectedAccountId] = useState<string>("");
  const [createCoaFormData, setCreateCoaFormData] = useState<{ account_name: string; account_type: string; account_code: string; description: string }>({
    account_name: "",
    account_type: "expense",
    account_code: "",
    description: "",
  });
  const [isCreatingCoa, setIsCreatingCoa] = useState<boolean>(false);
  const [showMathDiscrepancyModal, setShowMathDiscrepancyModal] = useState<boolean>(false);
  const [showRawJsonModal, setShowRawJsonModal] = useState<boolean>(false);
  const [copiedJson, setCopiedJson] = useState<boolean>(false);
  const [warningModalOpen, setWarningModalOpen] = useState<boolean>(false);
  const [activeWarnings, setActiveWarnings] = useState<string[]>([]);
  const [vendorStatus, setVendorStatus] = useState<InvoiceVendorStatusResponse | null>(null);
  const [vendorModalOpen, setVendorModalOpen] = useState<boolean>(false);
  const [isAddingVendor, setIsAddingVendor] = useState<boolean>(false);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);
  const [blobLoading, setBlobLoading] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    if (invoiceId) {
      setBlobLoading(true);
      fetchAuthenticatedFileBlobUrl(invoiceId)
        .then((blobUrl) => {
          if (active) {
            setPreviewBlobUrl(blobUrl);
            setBlobLoading(false);
          }
        })
        .catch(() => {
          if (active) {
            setPreviewBlobUrl(null);
            setBlobLoading(false);
          }
        });
    }
    return () => {
      active = false;
    };
  }, [invoiceId]);

  // Synchronize Line Items and General Ledger lines once Zoho master accounts are loaded
  useEffect(() => {
    if (zohoAccounts && zohoAccounts.length > 0 && formData.line_items && formData.line_items.length > 0) {
      // 1. Auto-fill accountingLines with matched Zoho account IDs
      setAccountingData((prev) => {
        const currentAcc = [...(prev.accounting || [])];
        let changed = false;
        formData.line_items?.forEach((item, idx) => {
          const acc = currentAcc[idx] || { line_index: idx + 1 };
          const predName = String(
            acc.approved_account_name ||
            acc.account_name ||
            acc.ai_account_name ||
            item.account_name ||
            ""
          ).replace(/^\[Unapproved\]\s*/i, "").trim();

          if (predName) {
            const matched = zohoAccounts.find(
              (za: any) => za.account_name?.toLowerCase().trim() === predName.toLowerCase()
            );
            if (matched) {
              const zohoId = String(matched.zoho_account_id || matched.id);
              const zohoName = matched.account_name;
              if (acc.account_id !== zohoId || acc.approved_account_id !== zohoId || acc.account_name !== zohoName) {
                currentAcc[idx] = {
                  ...acc,
                  account_id: zohoId,
                  approved_account_id: zohoId,
                  final_account_id: zohoId,
                  account_name: zohoName,
                  approved_account_name: zohoName,
                  final_account_name: zohoName,
                };
                changed = true;
              }
            }
          }
        });
        return changed ? { ...prev, accounting: currentAcc } : prev;
      });

      // 2. Auto-fill journalEntry.lines with matched Zoho accounts
      setJournalEntry((prev) => {
        if (!prev || !prev.lines) return prev;
        let jChanged = false;
        const jLines = prev.lines.map((l: any, idx: number) => {
          if (l.line_type === "EXPENSE" || !l.line_type) {
            const item = formData.line_items?.[idx] || {};
            const acc = (accountingData.accounting || [])[idx] || {};
            const predName = String(
              acc.approved_account_name ||
              acc.account_name ||
              acc.ai_account_name ||
              l.account_name ||
              item.account_name ||
              ""
            ).replace(/^\[Unapproved\]\s*/i, "").trim();

            const matched = zohoAccounts.find(
              (za: any) => za.account_name?.toLowerCase().trim() === predName.toLowerCase()
            );
            if (matched) {
              const zohoId = String(matched.zoho_account_id || matched.id);
              const zohoName = matched.account_name;
              if (l.account_id !== zohoId || l.account_name !== zohoName) {
                jChanged = true;
                return {
                  ...l,
                  account_id: zohoId,
                  account_name: zohoName,
                  match_status: "EXACT_MATCH",
                  ai_needs_review: false,
                };
              }
            }
          }
          return l;
        });
        return jChanged ? { ...prev, lines: jLines } : prev;
      });
    }
  }, [zohoAccounts]);

  useEffect(() => {
    if (!invoiceId) return;

    async function loadData() {
      try {
        setLoading(true);
        // 1. Fetch invoice first for instant rendering (<50ms)
        const invData = await getInvoice(invoiceId);
        setInvoice(invData);

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
        const getVlmPayload = (obj: any): any => {
          if (!obj || typeof obj !== "object") return {};
          let target = obj;
          if (target.data && typeof target.data === "object") target = target.data;
          if (target.prediction && typeof target.prediction === "object") target = target.prediction;
          return target;
        };

        const rawDataPayload = getVlmPayload(invData.raw_vlm_output);
        const currDataPayload = getVlmPayload(invData.current_vlm_output);

        const vDet = {
          ...(typeof rawDataPayload.vendor_details === "object" ? rawDataPayload.vendor_details : {}),
          ...(typeof currDataPayload.vendor_details === "object" ? currDataPayload.vendor_details : {}),
        };
        const cDet = {
          ...(typeof rawDataPayload.customer_details === "object" ? rawDataPayload.customer_details : {}),
          ...(typeof currDataPayload.customer_details === "object" ? currDataPayload.customer_details : {}),
        };
        const iDet = {
          ...(typeof rawDataPayload.invoice_details === "object" ? rawDataPayload.invoice_details : {}),
          ...(typeof currDataPayload.invoice_details === "object" ? currDataPayload.invoice_details : {}),
        };
        const fDet = {
          ...(typeof rawDataPayload.financial_details === "object" ? rawDataPayload.financial_details : {}),
          ...(typeof currDataPayload.financial_details === "object" ? currDataPayload.financial_details : {}),
        };

        const rawData: ExtractedInvoiceData = { ...rawDataPayload };
        const currData: ExtractedInvoiceData = { ...currDataPayload };

        // Merge raw extraction with user-edited fields, ensuring sub-objects and top level are flattened
        const extracted: ExtractedInvoiceData = {
          ...vDet,
          ...cDet,
          ...iDet,
          ...fDet,
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
        if (!extracted.vendor_name && vDet.vendor_name) extracted.vendor_name = vDet.vendor_name;
        if (!extracted.vendor_address && vDet.vendor_address) extracted.vendor_address = vDet.vendor_address;
        if (!extracted.vendor_gstin && vDet.vendor_gstin) extracted.vendor_gstin = vDet.vendor_gstin;
        if (!extracted.vendor_pan && vDet.vendor_pan) extracted.vendor_pan = vDet.vendor_pan;

        if (!extracted.vendor_phone) {
          extracted.vendor_phone =
            (vDet as any).vendor_phone ||
            (vDet as any).phone ||
            (vDet as any).mobile ||
            rawF.vendor_phone ||
            rawF.phone ||
            rawF.vendor_contact ||
            (rawData.additional_fields as any)?.vendor_phone ||
            (rawData.additional_fields as any)?.phone ||
            (currData.additional_fields as any)?.vendor_phone ||
            (currData.additional_fields as any)?.phone ||
            "";
        }
        if (!extracted.vendor_email) {
          extracted.vendor_email =
            (vDet as any).vendor_email ||
            (vDet as any).email ||
            rawF.vendor_email ||
            rawF.email ||
            (rawData.additional_fields as any)?.vendor_email ||
            (rawData.additional_fields as any)?.email ||
            (currData.additional_fields as any)?.vendor_email ||
            (currData.additional_fields as any)?.email ||
            "";
        }

        if (!extracted.customer_name && cDet.customer_name) extracted.customer_name = cDet.customer_name;
        if (!extracted.customer_address && cDet.customer_address) extracted.customer_address = cDet.customer_address;
        if (!extracted.customer_gstin && cDet.customer_gstin) extracted.customer_gstin = cDet.customer_gstin;
        if (!extracted.customer_pan && cDet.customer_pan) extracted.customer_pan = cDet.customer_pan;

        if (!extracted.customer_phone) {
          extracted.customer_phone =
            (cDet as any).customer_phone ||
            (cDet as any).phone ||
            (cDet as any).mobile ||
            rawF.customer_phone ||
            rawF.client_phone ||
            (rawData.additional_fields as any)?.customer_phone ||
            (currData.additional_fields as any)?.customer_phone ||
            "";
        }
        if (!extracted.customer_email) {
          extracted.customer_email =
            (cDet as any).customer_email ||
            (cDet as any).email ||
            rawF.customer_email ||
            rawF.client_email ||
            (rawData.additional_fields as any)?.customer_email ||
            (currData.additional_fields as any)?.customer_email ||
            "";
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
        const addBank =
          (typeof (rawData.additional_fields as any)?.bank_details === "object" ? (rawData.additional_fields as any).bank_details : null) ||
          (typeof (currData.additional_fields as any)?.bank_details === "object" ? (currData.additional_fields as any).bank_details : null);

        if (addBank) {
          if (!bankObj.bank_name) bankObj.bank_name = addBank.bank_name || addBank.bank;
          if (!bankObj.account_number) bankObj.account_number = addBank.account_number || addBank.account_no || addBank.a_c_no;
          if (!bankObj.ifsc_code) bankObj.ifsc_code = addBank.ifsc_code || addBank.ifsc;
          if (!bankObj.branch) bankObj.branch = addBank.branch || addBank.branch_name;
          if (!bankObj.branch_name) bankObj.branch_name = addBank.branch || addBank.branch_name;
          if (!bankObj.account_holder_name) bankObj.account_holder_name = addBank.account_holder_name || addBank.account_name;
        }

        const unparsedBankText: string =
          (typeof rawF.bank_details === "string" ? rawF.bank_details : "") ||
          (rawData.additional_fields as any)?.unparsed_bank_details ||
          (currData.additional_fields as any)?.unparsed_bank_details ||
          (typeof (rawData.additional_fields as any)?.bank_details === "string" ? (rawData.additional_fields as any).bank_details : "") ||
          (typeof rawData.bank_details === "string" ? rawData.bank_details : "") ||
          "";

        if (unparsedBankText) {
          if (!bankObj.bank_name) {
            const m = unparsedBankText.match(/Bank\s*(?:Name)?[:\s]*([^,\n|]+)/i);
            if (m) bankObj.bank_name = m[1].trim();
          }
          if (!bankObj.branch_name || !bankObj.branch) {
            const m = unparsedBankText.match(/Branch[:\s]*([^,\n|]+)/i) || unparsedBankText.match(/Bank:[^,]+,\s*([^,\n|]+)/i);
            if (m) {
              const val = m[1].trim();
              bankObj.branch_name = val;
              bankObj.branch = val;
            }
          }
          if (!bankObj.account_number) {
            const m = unparsedBankText.match(/(?:A\/C\s*No|Account\s*No|A\/c|Account(?:\s*No|\s*Number)?)[:.\s]*([0-9A-Za-z]+)/i);
            if (m) bankObj.account_number = m[1].trim();
          }
          if (!bankObj.ifsc_code) {
            const m = unparsedBankText.match(/IFSC\s*(?:Code)?[:.\s]*([A-Z]{4}0[A-Z0-9]{6})/i);
            if (m) bankObj.ifsc_code = m[1].trim();
          }
          if (!bankObj.account_holder_name) {
            const m = unparsedBankText.match(/Account\s*Name[:.\s]*([^,\n|]+)/i);
            if (m) bankObj.account_holder_name = m[1].trim();
          }
        }
        if (bankObj.branch_name && !bankObj.branch) bankObj.branch = bankObj.branch_name;
        if (bankObj.branch && !bankObj.branch_name) bankObj.branch_name = bankObj.branch;
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

        // Synchronize initial journal lines with predicted/extracted line item COA names
        let loadedJournal = invData.journal_entry || null;
        const actualAccLines = accOutput.accounting || [];
        if (loadedJournal && loadedJournal.lines && loadedJournal.lines.length > 0) {
          const syncedLines = loadedJournal.lines.map((jLine: any, idx: number) => {
            if (jLine.line_type === "EXPENSE" || !jLine.line_type) {
              const accLine = actualAccLines[idx] || {};
              const itemLine = extracted.line_items?.[idx] || {};
              const targetAccName =
                accLine.approved_account_name ||
                accLine.final_account_name ||
                accLine.account_name ||
                accLine.ai_account_name ||
                itemLine.account_name;

              if (targetAccName) {
                const cleanName = String(targetAccName).replace(/^\[Unapproved\]\s*/i, "").trim();
                return {
                  ...jLine,
                  account_name: cleanName,
                  match_status: jLine.match_status || "EXACT_MATCH",
                };
              }
            }
            return jLine;
          });
          loadedJournal = { ...loadedJournal, lines: syncedLines };
        }
        setJournalEntry(loadedJournal);

        // Dynamically trigger COA match using actual extracted line item account_name or accounting line
        const extractedAccName =
          actualAccLines[0]?.approved_account_name ||
          actualAccLines[0]?.account_name ||
          actualAccLines[0]?.ai_account_name ||
          extracted.line_items?.[0]?.account_name ||
          "";

        if (extractedAccName) {
          import("@/lib/api").then(({ matchZohoCOA }) => {
            matchZohoCOA({ account_name: extractedAccName })
              .then(setCoaMatchResult)
              .catch(() => null);
          });
        }
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
    setFormData((prev) => {
      const next = { ...prev, [field]: value };

      // Auto PAN extraction from GSTIN if PAN is missing or derived
      if (field === "vendor_gstin" && typeof value === "string") {
        const cleanedGstin = value.trim().toUpperCase();
        if (cleanedGstin.length === 15) {
          const autoPan = cleanedGstin.substring(2, 12);
          if (!prev.vendor_pan || prev.vendor_pan.length !== 10) {
            next.vendor_pan = autoPan;
          }
        }
        if (!next.place_of_supply) {
          const pos = derivePlaceOfSupply(cleanedGstin, prev.customer_gstin);
          if (pos) next.place_of_supply = pos;
        }
      }

      if (field === "customer_gstin" && typeof value === "string") {
        const cleanedGstin = value.trim().toUpperCase();
        if (cleanedGstin.length === 15) {
          const autoPan = cleanedGstin.substring(2, 12);
          if (!prev.customer_pan || prev.customer_pan.length !== 10) {
            next.customer_pan = autoPan;
          }
        }
        if (!next.place_of_supply) {
          const pos = derivePlaceOfSupply(prev.vendor_gstin, cleanedGstin);
          if (pos) next.place_of_supply = pos;
        }
      }

      // Real-time calculation for surrounding header financial fields when manually edited
      const finFields = ["subtotal", "cgst_amount", "sgst_amount", "igst_amount", "tax_total", "discount_amount", "discount", "round_off", "tds_rate", "tds_amount"];
      if (finFields.includes(field as string)) {
        const sub = parseCleanNumeric(next.subtotal) ?? 0;
        const cgst = parseCleanNumeric(next.cgst_amount) ?? 0;
        const sgst = parseCleanNumeric(next.sgst_amount) ?? 0;
        const igst = parseCleanNumeric(next.igst_amount) ?? 0;

        let taxTot = parseCleanNumeric(next.tax_total) ?? 0;
        if (field === "cgst_amount" || field === "sgst_amount" || field === "igst_amount" || field === "subtotal") {
          taxTot = Math.round((cgst + sgst + igst) * 100) / 100;
          next.tax_total = taxTot;
        }

        const disc = parseCleanNumeric((next as any).discount_amount ?? (next as any).discount) ?? 0;
        const rOff = parseCleanNumeric((next as any).round_off) ?? 0;

        if (field !== "total_amount") {
          next.total_amount = Math.round((sub + taxTot + rOff - disc) * 100) / 100;
        }

        if ((field as string) === "tds_rate" && sub > 0) {
          const tRate = parseCleanNumeric(value) ?? 0;
          (next as any).tds_amount = Math.round((sub * (tRate / 100)) * 100) / 100;
        } else if ((field as string) === "tds_amount" && sub > 0) {
          const tAmt = parseCleanNumeric(value) ?? 0;
          (next as any).tds_rate = Math.round(((tAmt / sub) * 100) * 100) / 100;
        }
      }

      return next;
    });
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
      const currentItem = { ...items[index], [field]: value };

      // 1. Quantity or Unit Price change -> Taxable Amount
      if (field === "quantity" || field === "unit_price") {
        const q = parseFloat(String(currentItem.quantity || 0));
        const u = parseFloat(String(currentItem.unit_price || 0));
        if (!isNaN(q) && !isNaN(u) && q >= 0 && u >= 0) {
          currentItem.taxable_amount = Math.round(q * u * 100) / 100;
        }
      }

      const taxable = Number(currentItem.taxable_amount || 0);

      // 2. Tax Rates change -> Tax Amounts
      if (field === "cgst_rate" || field === "quantity" || field === "unit_price" || field === "taxable_amount") {
        const rate = parseFloat(String(currentItem.cgst_rate || 0));
        if (!isNaN(rate) && rate > 0 && taxable > 0) {
          currentItem.cgst_amount = Math.round((taxable * (rate / 100)) * 100) / 100;
        }
      }
      if (field === "sgst_rate" || field === "quantity" || field === "unit_price" || field === "taxable_amount") {
        const rate = parseFloat(String(currentItem.sgst_rate || 0));
        if (!isNaN(rate) && rate > 0 && taxable > 0) {
          currentItem.sgst_amount = Math.round((taxable * (rate / 100)) * 100) / 100;
        }
      }
      if (field === "igst_rate" || field === "quantity" || field === "unit_price" || field === "taxable_amount") {
        const rate = parseFloat(String(currentItem.igst_rate || 0));
        if (!isNaN(rate) && rate > 0 && taxable > 0) {
          currentItem.igst_amount = Math.round((taxable * (rate / 100)) * 100) / 100;
        }
      }

      // 3. Tax Amount direct edit -> Auto calculate Tax Rate %
      if (field === "cgst_amount" && taxable > 0) {
        const amt = parseFloat(String(currentItem.cgst_amount || 0));
        if (!isNaN(amt)) {
          currentItem.cgst_rate = Math.round(((amt / taxable) * 100) * 100) / 100;
        }
      }
      if (field === "sgst_amount" && taxable > 0) {
        const amt = parseFloat(String(currentItem.sgst_amount || 0));
        if (!isNaN(amt)) {
          currentItem.sgst_rate = Math.round(((amt / taxable) * 100) * 100) / 100;
        }
      }
      if (field === "igst_amount" && taxable > 0) {
        const amt = parseFloat(String(currentItem.igst_amount || 0));
        if (!isNaN(amt)) {
          currentItem.igst_rate = Math.round(((amt / taxable) * 100) * 100) / 100;
        }
      }

      // 4. Calculate Line Total
      const cgst = Number(currentItem.cgst_amount || 0);
      const sgst = Number(currentItem.sgst_amount || 0);
      const igst = Number(currentItem.igst_amount || 0);
      const cess = Number((currentItem as any).cess_amount || 0);
      const disc = Number(currentItem.discount || 0);

      currentItem.total = Math.round((taxable + cgst + sgst + igst + cess - disc) * 100) / 100;
      items[index] = currentItem;

      // 5. Recalculate Header Totals without wiping header taxes if line items lack per-line tax
      const sumSubtotal = items.reduce((acc, it) => acc + (Number(it.taxable_amount) || 0), 0);
      const sumCgst = items.reduce((acc, it) => acc + (Number(it.cgst_amount) || 0), 0);
      const sumSgst = items.reduce((acc, it) => acc + (Number(it.sgst_amount) || 0), 0);
      const sumIgst = items.reduce((acc, it) => acc + (Number(it.igst_amount) || 0), 0);
      const sumTax = sumCgst + sumSgst + sumIgst;

      const hasPerLineTax = items.some(it => 
        (Number(it.cgst_amount) || 0) > 0 || 
        (Number(it.sgst_amount) || 0) > 0 || 
        (Number(it.igst_amount) || 0) > 0 ||
        (Number(it.cgst_rate) || 0) > 0 || 
        (Number(it.sgst_rate) || 0) > 0 || 
        (Number(it.igst_rate) || 0) > 0
      );

      const nextSubtotal = sumSubtotal > 0 ? Math.round(sumSubtotal * 100) / 100 : (prev.subtotal ?? 0);
      const nextCgst = hasPerLineTax ? Math.round(sumCgst * 100) / 100 : (prev.cgst_amount ?? (prev as any).cgst ?? 0);
      const nextSgst = hasPerLineTax ? Math.round(sumSgst * 100) / 100 : (prev.sgst_amount ?? (prev as any).sgst ?? 0);
      const nextIgst = hasPerLineTax ? Math.round(sumIgst * 100) / 100 : (prev.igst_amount ?? (prev as any).igst ?? 0);
      
      const nextTaxTotal = hasPerLineTax 
        ? Math.round(sumTax * 100) / 100 
        : (prev.tax_total ?? Math.round(((Number(nextCgst) || 0) + (Number(nextSgst) || 0) + (Number(nextIgst) || 0)) * 100) / 100);
        
      const nextTotal = Math.round(((Number(nextSubtotal) || 0) + (Number(nextTaxTotal) || 0)) * 100) / 100;

      return {
        ...prev,
        line_items: items,
        subtotal: nextSubtotal,
        cgst_amount: nextCgst,
        sgst_amount: nextSgst,
        igst_amount: nextIgst,
        tax_total: nextTaxTotal,
        total_amount: nextTotal,
      };
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
  const updateAccountingLine = (index: number, updates: Partial<AccountingLineItem>) => {
    setAccountingData((prev) => {
      const baseLines = (prev.accounting && prev.accounting.length > 0)
        ? prev.accounting
        : (invoice?.current_accounting_output?.accounting || invoice?.accounting_output?.accounting || formData.line_items?.map((li: any, i: number) => ({
          line_index: i + 1,
          source_description: li.description,
          account_id: null,
          account_name: null,
        })) || []);
      const list = [...baseLines];
      while (list.length <= index) {
        list.push({ line_index: list.length + 1, source_description: "", account_id: null, account_name: null });
      }
      const updatedItem = { ...list[index], ...updates };
      list[index] = updatedItem;

      // Bi-directionally sync to journalEntry.lines
      const newAccId = updatedItem.approved_account_id || updatedItem.account_id;
      const newAccName = updatedItem.approved_account_name || updatedItem.account_name;
      if (newAccName || newAccId) {
        setJournalEntry((jPrev: any) => {
          if (!jPrev || !jPrev.lines) return jPrev;
          const jLines = [...jPrev.lines];
          if (jLines[index]) {
            jLines[index] = {
              ...jLines[index],
              account_id: newAccId || jLines[index].account_id,
              account_name: newAccName || jLines[index].account_name,
              match_status: "EXACT_MATCH",
              ai_needs_review: false,
              provenance: "HUMAN_APPROVED",
            };
          }
          return { ...jPrev, lines: jLines };
        });
      }

      return { ...prev, accounting: list };
    });
  };

  const handleAccountingItemChange = (
    index: number,
    field: keyof AccountingLineItem,
    value: any
  ) => {
    updateAccountingLine(index, { [field]: value });
  };

  // COA uncertainty checking helper
  const isUncertainCoaLine = (line: any) => {
    if (!line) return false;
    // System lines (Input Tax, Accounts Payable, TDS Payable) generated deterministically do not require user COA review
    if (
      line.line_type === "INPUT_TAX" ||
      line.line_type === "ACCOUNTS_PAYABLE" ||
      line.line_type === "TDS_PAYABLE" ||
      line.provenance === "DETERMINISTIC"
    ) {
      return false;
    }
    // If user explicitly approved or edited manually, it's confirmed!
    if (line.provenance === "HUMAN_APPROVED" || line.provenance === "CUSTOMER_EDIT" || line.provenance === "HITL_OVERRIDE") {
      return false;
    }
    // If line has explicit EXACT_MATCH status and not flagged for review
    if (line.match_status === "EXACT_MATCH" && !line.ai_needs_review && !String(line.account_name || "").includes("[Unapproved]")) {
      return false;
    }
    // Flag as uncertain if missing account_id AND account_name, or if explicitly unselected/unassigned
    const accName = String(line.account_name || "").trim();
    if (!line.account_id || line.account_id === "" || line.account_id === "ACC_MANUAL" || line.account_id === "ACC_EXPENSE") {
      if (!accName || accName === "-- Select Account --" || accName === "Unassigned COA" || accName.includes("[Unapproved]")) {
        return true;
      }
    }
    if (accName === "-- Select Account --" || accName === "Unassigned COA" || accName.includes("[Unapproved]")) {
      return true;
    }
    if (line.match_status && line.match_status !== "EXACT_MATCH" && line.match_status !== "MATCHED") {
      return true;
    }
    if (line.ai_needs_review) {
      return true;
    }
    return false;
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

      // Bi-directionally sync account changes to accountingLines/line_items
      if (field === "account_id" || field === "account_name") {
        const srcIdx = typeof updatedLine.source_line_index === "number" ? updatedLine.source_line_index - 1 : index;
        if (srcIdx >= 0) {
          setAccountingData((accPrev: any) => {
            const list = [...(accPrev.accounting || [])];
            while (list.length <= srcIdx) {
              list.push({ line_index: list.length + 1, source_description: "", account_id: null, account_name: null });
            }
            list[srcIdx] = {
              ...list[srcIdx],
              approved_account_id: field === "account_id" ? value : list[srcIdx].approved_account_id,
              approved_account_name: field === "account_name" ? value : list[srcIdx].approved_account_name,
              account_id: field === "account_id" ? value : list[srcIdx].account_id,
              account_name: field === "account_name" ? value : list[srcIdx].account_name,
            };
            return { ...accPrev, accounting: list };
          });
        }
      }

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
      const isPercentDisc = (item as any).discount_type === "percentage" || String((item as any).discount || "").includes("%");
      let taxable = typeof item.taxable_amount === "number" ? item.taxable_amount : parseFloat(String(item.taxable_amount || ""));
      if (isNaN(taxable) || taxable === 0) {
        const gross = qty * price;
        const discAmt = isPercentDisc ? (gross * disc) / 100 : disc;
        taxable = Math.max(0, Math.round((gross - discAmt) * 100) / 100);
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
    const rawRate = tdsRaw.approved_tds_rate ?? tdsRaw.tds_rate ?? tdsRaw.rate;
    const secStr = String(tdsRaw.tds_section || tdsRaw.tds_provision || tdsRaw.nature_of_payment || "").toUpperCase();
    const fallbackRate = (secStr.includes("194Q") || secStr.includes("GOODS")) ? 0.1 : (secStr.includes("194I") || secStr.includes("RENT")) ? 10.0 : 2.0;
    const tdsRate = tdsApp
      ? (rawRate !== null && rawRate !== undefined && parseFloat(String(rawRate)) > 0
          ? parseFloat(String(rawRate))
          : fallbackRate)
      : 0;
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
        const rawPredicted =
          acc.approved_account_name ||
          acc.final_account_name ||
          acc.account_name ||
          acc.ai_account_name ||
          item.account_name ||
          (item.description || `Line ${idx + 1} Expense`);
        const predictedCoaName = String(rawPredicted || "").replace(/^\[Unapproved\]\s*/i, "").trim();

        const matchedZoho = zohoAccounts.find(
          (za: any) =>
            za.account_name?.toLowerCase().trim() === predictedCoaName?.toLowerCase().trim()
        ) || zohoAccounts.find(
          (za: any) =>
            String(za.zoho_account_id) === String(acc.approved_account_id || acc.account_id || (item as any).account_id)
        );

        const accId =
          acc.approved_account_id ||
          acc.final_account_id ||
          acc.account_id ||
          matchedZoho?.zoho_account_id ||
          (item as any).account_id ||
          (item as any).zoho_account_id ||
          zohoAccounts?.[0]?.zoho_account_id ||
          "ACC_EXPENSE";

        const accName =
          matchedZoho?.account_name ||
          predictedCoaName ||
          zohoAccounts?.[0]?.account_name ||
          "General Expenses";

        newJournalLines.push({
          account_id: accId,
          account_name: accName,
          line_type: "EXPENSE",
          debit: item.taxable_amount || 0,
          credit: 0,
          source_line_index: idx + 1,
          description: item.description || `Line ${idx + 1} Expense`,
          provenance: acc.approved_account_name || item.account_name ? "HUMAN_APPROVED" : "DETERMINISTIC",
          match_status: "EXACT_MATCH",
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

  // Real Zoho Export Action Handler
  const handleExport = async () => {
    if (invoice?.approval_status !== "APPROVED") {
      setError("Invoice must be approved by Finance before exporting to Zoho Books.");
      return;
    }

    const isJournalApproved =
      journalEntry &&
      (journalEntry.status === "APPROVED" || journalEntry.approval_status === "APPROVED");
    if (!isJournalApproved) {
      setError("Invoice cannot be exported without an approved, balanced General Ledger journal entry.");
      return;
    }

    // Strict Vendor match guard: Stop export if vendor is not matched in Zoho
    if (vendorStatus && vendorStatus.is_zoho_connected && vendorStatus.match_status !== "MATCHED") {
      setVendorModalOpen(true);
      setError("Vendor verification required: Please check vendor details or add the vendor to Zoho Books before exporting.");
      return;
    }

    try {
      setIsExporting(true);
      setError(null);

      const res = await exportInvoiceToZoho(invoiceId);
      setActionNotice(`Successfully exported to Zoho Books! Bill #${res.zoho_bill_number || res.zoho_bill_id}`);

      const updatedInv = await getInvoice(invoiceId);
      setInvoice(updatedInv);
    } catch (err: any) {
      const rawMsg = err.message || "Failed to export invoice to Zoho Books.";
      const handledLocally = handleFieldErrorOrExportError(rawMsg);
      if (!handledLocally) {
        setError(rawMsg);
      }
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
    tds_base_amount: null,
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
          {/* TOP SUMMARY BANNER: MATHEMATICAL VALIDATION & ZOHO COA MATCHING */}
          {/* ==================================================== */}
          <div style={{ marginBottom: "20px", display: "flex", flexDirection: "column", gap: "12px" }}>

            {/* 1. MATHEMATICAL VALIDATION CARD (ONLY SHOWN IF INCORRECT FIELDS EXIST) */}
            {(() => {
              const valStatus = financialValidationResult?.validation_status || (
                financialValidationResult?.overall_status === "PASSED"
                  ? "VALID"
                  : financialValidationResult?.overall_status === "MISMATCH"
                    ? "MISMATCH"
                    : "PARTIAL"
              );

              const isMismatch = valStatus === "MISMATCH" || financialValidationResult?.overall_status === "MISMATCH";

              // Only show this message banner if there are fields which are incorrect
              if (!isMismatch) return null;

              const failedChecks = (financialValidationResult?.checks || []).filter(
                (c: any) => c.status === "MISMATCH" || c.status === "FAILED"
              );
              const errorsList = financialValidationResult?.errors || [];

              return (
                <div
                  className="card"
                  style={{
                    padding: "14px 18px",
                    backgroundColor: "#fef2f2",
                    borderColor: "rgba(239, 68, 68, 0.4)",
                    borderWidth: "1.5px",
                    borderRadius: "10px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "10px", flex: 1 }}>
                      <AlertCircle size={20} style={{ color: "#ef4444", marginTop: "2px", flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: "700", fontSize: "14px", color: "#b91c1c" }}>
                          ⚠ Mathematical Discrepancy Detected — Incorrect Fields Found
                        </div>
                        <div style={{ fontSize: "12px", color: "#991b1b", marginTop: "4px", lineHeight: "1.5" }}>
                          The following extracted invoice fields do not reconcile with calculated values:
                        </div>

                        {/* List of failed checks showing where and what is incorrect */}
                        <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "6px" }}>
                          {failedChecks.length > 0 ? (
                            failedChecks.map((chk: any, idx: number) => (
                              <div
                                key={idx}
                                style={{
                                  fontSize: "12px",
                                  backgroundColor: "#ffffff",
                                  border: "1px solid #fca5a5",
                                  padding: "6px 10px",
                                  borderRadius: "6px",
                                  color: "#7f1d1d",
                                }}
                              >
                                <strong>Location / Field:</strong> {chk.field || chk.type || chk.name || "Invoice Line / Total"}
                                {chk.invoice_value !== undefined && chk.calculated_value !== undefined && (
                                  <span style={{ marginLeft: "8px" }}>
                                    (Extracted: <strong>₹{Number(chk.invoice_value).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong> vs Calculated: <strong>₹{Number(chk.calculated_value).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong> | Diff: <strong style={{ color: "#dc2626" }}>₹{Number(chk.difference || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>)
                                  </span>
                                )}
                                {chk.message && <div style={{ fontSize: "11px", color: "#991b1b", marginTop: "2px" }}>{chk.message}</div>}
                              </div>
                            ))
                          ) : errorsList.length > 0 ? (
                            errorsList.map((err: string, idx: number) => (
                              <div
                                key={idx}
                                style={{
                                  fontSize: "12px",
                                  backgroundColor: "#ffffff",
                                  border: "1px solid #fca5a5",
                                  padding: "6px 10px",
                                  borderRadius: "6px",
                                  color: "#7f1d1d",
                                }}
                              >
                                • {err}
                              </div>
                            ))
                          ) : (
                            <div
                              style={{
                                fontSize: "12px",
                                backgroundColor: "#ffffff",
                                border: "1px solid #fca5a5",
                                padding: "6px 10px",
                                borderRadius: "6px",
                                color: "#7f1d1d",
                              }}
                            >
                              • Extracted line item subtotals or tax values do not balance with the invoice total amount.
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => setShowMathDiscrepancyModal(true)}
                      className="btn btn-secondary"
                      style={{
                        padding: "6px 14px",
                        fontSize: "11px",
                        borderColor: "#ef4444",
                        color: "#ef4444",
                        fontWeight: 600,
                        flexShrink: 0,
                      }}
                    >
                      View Math Details
                    </button>
                  </div>
                </div>
              );
            })()}

            {/* 2. ZOHO CHART OF ACCOUNTS (COA) VERIFICATION BANNER */}
            {(() => {
              const firstLineAcc = accountingLines[0];
              const primaryAccName =
                firstLineAcc?.approved_account_name ||
                firstLineAcc?.account_name ||
                firstLineAcc?.ai_account_name ||
                formData?.line_items?.[0]?.account_name ||
                "Unassigned COA";
              const matchStatus = coaMatchResult?.match_status || (zohoAccounts.some((za: any) => za.account_name?.toLowerCase().trim() === primaryAccName.toLowerCase().trim()) ? "EXACT_MATCH" : "NO_MATCH");

              // If COA is 100% exact match, hide popup banner box (kept in line items dropdown to edit if needed)
              if (matchStatus === "EXACT_MATCH") return null;

              const matchedAcc = coaMatchResult?.matched_account || zohoAccounts.find((za: any) => za.account_name?.toLowerCase().trim() === primaryAccName.toLowerCase().trim());
              const suggestedAcc = coaMatchResult?.suggested_account;
              const conflictingAcc = coaMatchResult?.conflicting_account;

              let bannerBg = "rgba(2, 132, 199, 0.05)";
              let bannerBorder = "rgba(2, 132, 199, 0.2)";
              let statusText = "Zoho Chart of Accounts Status";

              if (matchStatus === "EXACT_MATCH") {
                bannerBg = "rgba(16, 185, 129, 0.05)";
                bannerBorder = "rgba(16, 185, 129, 0.2)";
              } else if (matchStatus === "SUGGESTED_MATCH") {
                bannerBg = "rgba(245, 158, 11, 0.05)";
                bannerBorder = "rgba(245, 158, 11, 0.2)";
              } else if (matchStatus === "COA_CONFLICT") {
                bannerBg = "rgba(239, 68, 68, 0.05)";
                bannerBorder = "rgba(239, 68, 68, 0.2)";
              }

              return (
                <div
                  className="card"
                  style={{
                    padding: "14px 18px",
                    backgroundColor: bannerBg,
                    borderColor: bannerBorder,
                    borderRadius: "10px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <BookOpen size={18} style={{ color: matchStatus === "EXACT_MATCH" ? "#10b981" : matchStatus === "SUGGESTED_MATCH" ? "#f59e0b" : matchStatus === "COA_CONFLICT" ? "#ef4444" : "#0284c7" }} />
                    <div>
                      <div style={{ fontWeight: "700", fontSize: "13px", color: "var(--text-primary)" }}>
                        {matchStatus === "EXACT_MATCH" && "✓ Extracted COA Exactly Matches Zoho COA"}
                        {matchStatus === "SUGGESTED_MATCH" && "⚠ No Exact Zoho COA Match Found"}
                        {matchStatus === "COA_CONFLICT" && "⛔ Account Type Conflict Detected"}
                        {matchStatus === "NO_MATCH" && "ℹ No Matching Zoho COA Found"}
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                        {matchStatus === "EXACT_MATCH" && (
                          <span>
                            Extracted: <strong>'{primaryAccName}'</strong> → Matched Zoho: <strong>'{matchedAcc?.account_name}'</strong> {matchedAcc?.account_code ? `(${matchedAcc.account_code})` : ""}
                          </span>
                        )}
                        {matchStatus === "SUGGESTED_MATCH" && (
                          <span>
                            Extracted: <strong>'{primaryAccName}'</strong> | Suggested Closest Zoho: <strong>'{suggestedAcc?.account_name}'</strong> ({suggestedAcc?.account_type || "expense"}) {coaMatchResult?.similarity_score ? `[${Math.round(coaMatchResult.similarity_score * 100)}% Match]` : ""}
                          </span>
                        )}
                        {matchStatus === "COA_CONFLICT" && (
                          <span>
                            Account name matches <strong>'{conflictingAcc?.account_name}'</strong>, but extracted type conflicts with Zoho type <strong>'{conflictingAcc?.account_type}'</strong>.
                          </span>
                        )}
                        {matchStatus === "NO_MATCH" && (
                          <span>
                            No active Zoho account matches extracted COA <strong>'{primaryAccName}'</strong>.
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "8px" }}>
                    {/* Approve Suggested COA Button (only when SUGGESTED_MATCH exists) */}
                    {matchStatus === "SUGGESTED_MATCH" && suggestedAcc?.zoho_account_id && (
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            setIsSaving(true);
                            const { assignInvoiceCOA } = await import("@/lib/api");
                            const res = await assignInvoiceCOA(invoiceId, {
                              zoho_account_id: suggestedAcc.zoho_account_id,
                              account_name: suggestedAcc.account_name,
                              account_type: suggestedAcc.account_type || "expense",
                              account_code: suggestedAcc.account_code,
                            });
                            setInvoice(res);
                            if (res.current_accounting_output) setAccountingData(res.current_accounting_output);
                            setActionNotice(`✓ Approved & persisted suggested COA '${suggestedAcc.account_name}'!`);
                            setTimeout(() => setActionNotice(null), 4000);
                          } catch (err: any) {
                            setError(err.message || "Failed to approve COA mapping.");
                          } finally {
                            setIsSaving(false);
                          }
                        }}
                        className="btn btn-secondary"
                        style={{ padding: "5px 10px", fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "4px", borderColor: "#10b981", color: "#10b981" }}
                      >
                        <Check size={12} />
                        <span>Approve Suggested COA</span>
                      </button>
                    )}

                    {/* Create New COA Modal Trigger */}
                    <button
                      type="button"
                      onClick={() => {
                        setCreateCoaFormData({
                          account_name: primaryAccName,
                          account_type: "expense",
                          account_code: "",
                          description: `Created from invoice ${formData?.invoice_number || invoiceId}`,
                        });
                        setShowCreateCoaModal(true);
                      }}
                      className="btn btn-secondary"
                      style={{ padding: "5px 10px", fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "4px" }}
                    >
                      <Plus size={12} />
                      <span>Create New COA in Zoho</span>
                    </button>
                  </div>
                </div>
              );
            })()}

          </div>

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
                {blobLoading ? (
                  <div style={{ flex: 1, height: "100%", minHeight: "800px", display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", color: "var(--text-secondary)" }}>
                    <RefreshCw size={20} className="animate-spin" /> Loading document preview...
                  </div>
                ) : isPdf ? (
                  <object
                    data={previewBlobUrl || fileUrl}
                    type="application/pdf"
                    style={{ width: "100%", height: "100%", minHeight: "800px", border: "none" }}
                  >
                    <iframe
                      src={previewBlobUrl || fileUrl}
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
                      src={previewBlobUrl || fileUrl}
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
                {/* Left: AI Extraction Review Title & Badges */}
                <div style={{ minWidth: "0" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "2px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "11px", fontWeight: "700", letterSpacing: "0.06em", color: "var(--text-secondary)", textTransform: "uppercase" }}>
                      AI Extraction Review
                    </span>
                    {(!invoice?.approval_status || invoice?.approval_status === "PENDING") && (
                      <span className="badge" style={{ fontSize: "10px", display: "inline-flex", alignItems: "center", gap: "3px", background: "#fef3c7", color: "#d97706", border: "1px solid #fde68a" }}>
                        <Clock size={10} /> Pending Review
                      </span>
                    )}
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
                  <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    Final Invoice & Accounting Workspace
                  </div>
                </div>

                {/* Right: Compact Accounting Period Block */}
                {(() => {
                  const invDate = formData.invoice_date || invoice?.invoice_date;
                  const periodInfo = getAccountingPeriodInfo(invDate, invoice?.period_category);
                  if (!periodInfo) return null;

                  return (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "6px 12px",
                        borderRadius: "8px",
                        background: periodInfo.isPreviousFy ? "#fef2f2" : "#f8fafc",
                        border: `1px solid ${periodInfo.isPreviousFy ? "#fecaca" : "var(--border-subtle)"}`,
                        flexShrink: 0,
                        marginLeft: "16px",
                      }}
                    >
                      <div
                        style={{
                          width: "28px",
                          height: "28px",
                          borderRadius: "6px",
                          background: periodInfo.isPreviousFy ? "#fee2e2" : "#e2e8f0",
                          color: periodInfo.isPreviousFy ? "#dc2626" : "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <Calendar size={14} />
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", textAlign: "right" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "6px" }}>
                          <span style={{ fontSize: "10px", fontWeight: "700", letterSpacing: "0.04em", color: "var(--text-secondary)", textTransform: "uppercase" }}>
                            Accounting Period
                          </span>
                        </div>
                        <div style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-primary)", lineHeight: "1.2" }}>
                          {periodInfo.monthYear}
                        </div>
                        <div
                          style={{
                            fontSize: "11px",
                            fontWeight: "500",
                            color: periodInfo.isPreviousFy ? "#b91c1c" : "#16a34a",
                            lineHeight: "1.2",
                            marginTop: "1px",
                          }}
                        >
                          {periodInfo.fyStatus}
                        </div>
                      </div>
                    </div>
                  );
                })()}
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
                        placeholder="DD-MM-YYYY"
                        onChange={(e) => handleFieldChange("invoice_date", e.target.value)}
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

                    {/* Vendor Bank Details Sub-block */}
                    <div style={{ gridColumn: "span 2", background: "#f8fafc", padding: "10px 12px", borderRadius: "6px", border: "1px solid #e2e8f0", marginTop: "4px" }}>
                      <div style={{ fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "8px" }}>
                        🏦 Vendor Bank Account Details
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                        <div>
                          <label className="form-label" style={{ fontSize: "11px" }}>Bank Name</label>
                          <input
                            type="text"
                            className="form-input"
                            style={{ fontSize: "11.5px" }}
                            value={formData.bank_details?.bank_name ?? ""}
                            placeholder="e.g. HDFC Bank"
                            onChange={(e) => handleFieldChange("bank_details", { ...(formData.bank_details || {}), bank_name: e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="form-label" style={{ fontSize: "11px" }}>Account Number</label>
                          <input
                            type="text"
                            className="form-input"
                            style={{ fontSize: "11.5px" }}
                            value={formData.bank_details?.account_number ?? ""}
                            placeholder="Account Number"
                            onChange={(e) => handleFieldChange("bank_details", { ...(formData.bank_details || {}), account_number: e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="form-label" style={{ fontSize: "11px" }}>IFSC Code</label>
                          <input
                            type="text"
                            className="form-input"
                            style={{ fontSize: "11.5px" }}
                            value={formData.bank_details?.ifsc_code ?? ""}
                            placeholder="IFSC Code"
                            onChange={(e) => handleFieldChange("bank_details", { ...(formData.bank_details || {}), ifsc_code: e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="form-label" style={{ fontSize: "11px" }}>Branch</label>
                          <input
                            type="text"
                            className="form-input"
                            style={{ fontSize: "11.5px" }}
                            value={formData.bank_details?.branch ?? ""}
                            placeholder="Branch Name"
                            onChange={(e) => handleFieldChange("bank_details", { ...(formData.bank_details || {}), branch: e.target.value })}
                          />
                        </div>
                      </div>
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
                    <div>
                      <label className="form-label">Customer Phone</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.customer_phone ?? ""}
                        placeholder="Phone / Mobile"
                        onChange={(e) => handleFieldChange("customer_phone", e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Customer Email</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.customer_email ?? ""}
                        placeholder="Email Address"
                        onChange={(e) => handleFieldChange("customer_email", e.target.value)}
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
                      {(() => {
                        const unmappedCount = (formData.line_items || []).filter((_, i) => {
                          const acc = accountingLines[i] || {};
                          return !(acc.approved_account_id || acc.account_id) || String(acc.account_id) === "None" || String(acc.approved_account_id) === "None";
                        }).length;
                        if (unmappedCount > 0) {
                          return (
                            <span className="badge" style={{ fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "4px", background: "#ffffff", color: "#dc2626", border: "1.5px solid #ef4444", fontWeight: 700 }}>
                              <AlertTriangle size={13} style={{ color: "#ef4444" }} />
                              <span>⚠️ {unmappedCount} {unmappedCount === 1 ? "item needs" : "items need"} COA Account</span>
                            </span>
                          );
                        }
                        return null;
                      })()}
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
                          <th style={{ padding: "10px 8px", minWidth: "210px" }}>Expense Account (COA)</th>
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
                            const itemErrorMsg = lineItemErrors[idx];
                            const isAccMissing = !(acc.approved_account_id || acc.account_id) || String(acc.account_id) === "None" || String(acc.approved_account_id) === "None";
                            const isFieldInError = Boolean(itemErrorMsg) || isAccMissing;
                            return (
                              <tr key={idx} id={`line-item-row-${idx}`} style={{ borderBottom: "1px solid #e2e8f0", background: "#ffffff" }}>
                                <td style={{ padding: "6px", textAlign: "center" }}>
                                  {isFieldInError ? (
                                    <span title="Action required: Select Chart of Accounts account" style={{ color: "#ef4444", fontWeight: "800", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "2px" }}>
                                      <AlertTriangle size={13} style={{ flexShrink: 0 }} /> {idx + 1}
                                    </span>
                                  ) : (
                                    <span style={{ color: "var(--text-tertiary)" }}>{idx + 1}</span>
                                  )}
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
                                {(mode as string) !== "hitl_extraction" && (
                                  <td style={{ padding: "6px" }}>
                                    {zohoAccounts && zohoAccounts.length > 0 ? (
                                      <div>
                                        <select
                                          className="table-input"
                                          style={{
                                            background: "#ffffff",
                                            border: isFieldInError ? "2px solid #ef4444" : "1px solid #cbd5e1",
                                            borderRadius: "6px",
                                            padding: "5px 8px",
                                            width: "100%",
                                            fontSize: "12px",
                                            fontWeight: isFieldInError ? "600" : "500",
                                            color: isFieldInError ? "#dc2626" : "#0f172a",
                                            boxShadow: isFieldInError ? "0 0 0 3px rgba(239, 68, 68, 0.15)" : "none",
                                            cursor: "pointer",
                                          }}
                                          value={(() => {
                                            const curId = String(acc.approved_account_id || acc.final_account_id || acc.account_id || "").trim();
                                            if (curId && curId !== "None" && curId !== "PROPOSED" && curId !== "null" && curId !== "undefined") {
                                              if (zohoAccounts.some((za: any) => String(za.zoho_account_id || za.id).trim() === curId)) {
                                                return curId;
                                              }
                                            }
                                            const curName = String(acc.approved_account_name || acc.final_account_name || acc.account_name || acc.ai_account_name || "").toLowerCase().trim();
                                            if (curName && curName !== "none" && curName !== "null") {
                                              const matched = zohoAccounts.find((za: any) => String(za.account_name || "").toLowerCase().trim() === curName);
                                              if (matched) return String(matched.zoho_account_id || matched.id);
                                            }
                                            return "";
                                          })()}
                                          onChange={(e) => {
                                            setLineItemErrors((prev) => {
                                              const next = { ...prev };
                                              delete next[idx];
                                              return next;
                                            });
                                            const selId = e.target.value;
                                            const match = zohoAccounts.find((za: any) => String(za.zoho_account_id || za.id) === String(selId));
                                            const selName = match ? match.account_name : selId;
                                            updateAccountingLine(idx, {
                                              approved_account_id: selId,
                                              approved_account_name: selName,
                                              final_account_id: selId,
                                              final_account_name: selName,
                                              account_id: selId,
                                              account_name: selName,
                                              line_index: idx + 1,
                                            });
                                          }}
                                        >
                                          <option value="">⚠️ Select COA Account (Required)</option>
                                          {/* Custom AI option if not directly in zoho master list */}
                                          {(acc.approved_account_name || acc.account_name || acc.ai_account_name) && !zohoAccounts.some((za: any) => String(za.zoho_account_id) === String(acc.account_id) || za.account_name.toLowerCase().trim() === String(acc.approved_account_name || acc.final_account_name || acc.account_name || acc.ai_account_name || "").toLowerCase().trim()) && (
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

                                        {itemErrorMsg && (
                                          <div
                                            style={{
                                              marginTop: "4px",
                                              padding: "4px 8px",
                                              background: "#fee2e2",
                                              border: "1px solid #fca5a5",
                                              borderRadius: "4px",
                                              color: "#b91c1c",
                                              fontSize: "10.5px",
                                              fontWeight: "700",
                                              display: "flex",
                                              alignItems: "flex-start",
                                              gap: "4px",
                                              boxShadow: "0 2px 4px rgba(239,68,68,0.15)",
                                            }}
                                          >
                                            <AlertTriangle size={12} style={{ flexShrink: 0, color: "#dc2626", marginTop: "1px" }} />
                                            <span>{itemErrorMsg}</span>
                                          </div>
                                        )}
                                        {(() => {
                                           const currentAccId = String(acc.approved_account_id || acc.account_id || "");
                                           const currentAccName = (
                                             zohoAccounts.find((za: any) => String(za.zoho_account_id || za.id) === currentAccId)?.account_name ||
                                             acc.approved_account_name ||
                                             acc.final_account_name ||
                                             acc.account_name ||
                                             ""
                                           );

                                           const sugName = acc.ai_account_name || acc.account_name || "";
                                           const isExactSelected = Boolean(
                                             currentAccName &&
                                             sugName &&
                                             currentAccName.toLowerCase().trim() === sugName.toLowerCase().trim()
                                           );

                                           // 1. If COA is 100% matching:
                                           if (isExactSelected) {
                                             return (
                                               <div
                                                 style={{
                                                   display: "flex",
                                                   alignItems: "center",
                                                   gap: "5px",
                                                   marginTop: "4px",
                                                   padding: "3px 7px",
                                                   background: "#f0fdf4",
                                                   border: "1px solid #bbf7d0",
                                                   borderRadius: "4px",
                                                   fontSize: "10.5px",
                                                   color: "#15803d",
                                                   fontWeight: 600,
                                                 }}
                                               >
                                                 <CheckCircle2 size={12} color="#16a34a" style={{ flexShrink: 0 }} />
                                                 <span>I matched this line item with '{currentAccName}' COA.</span>
                                               </div>
                                             );
                                           }

                                           // 2. If COA is uncertain / mapped to nearest:
                                           if (sugName) {
                                             return (
                                               <div
                                                 style={{
                                                   display: "flex",
                                                   alignItems: "center",
                                                   justifyContent: "space-between",
                                                   gap: "6px",
                                                   marginTop: "4px",
                                                   padding: "4px 8px",
                                                   background: "#fffbeb",
                                                   border: "1px solid #fde68a",
                                                   borderRadius: "4px",
                                                   fontSize: "10.5px",
                                                   color: "#b45309",
                                                 }}
                                               >
                                                 <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                                   <AlertTriangle size={12} color="#d97706" style={{ flexShrink: 0 }} />
                                                   <span>I mapped COA to nearest '{sugName}'. Edit if needed.</span>
                                                 </div>
                                                 <button
                                                   type="button"
                                                   onClick={() => {
                                                     setLineItemErrors((prev) => {
                                                       const next = { ...prev };
                                                       delete next[idx];
                                                       return next;
                                                     });
                                                     const match = zohoAccounts.find((za: any) => String(za.account_name || "").toLowerCase().trim() === String(sugName).toLowerCase().trim()) || zohoAccounts[0];
                                                     if (match) {
                                                       const selId = String(match.zoho_account_id || match.id);
                                                       const selName = match.account_name;
                                                       updateAccountingLine(idx, {
                                                         approved_account_id: selId,
                                                         approved_account_name: selName,
                                                         final_account_id: selId,
                                                         final_account_name: selName,
                                                         account_id: selId,
                                                         account_name: selName,
                                                         line_index: idx + 1,
                                                       });
                                                     }
                                                   }}
                                                   style={{
                                                     padding: "1px 6px",
                                                     fontSize: "9.5px",
                                                     fontWeight: 700,
                                                     backgroundColor: "#fef3c7",
                                                     color: "#92400e",
                                                     border: "1px solid #fcd34d",
                                                     borderRadius: "4px",
                                                     cursor: "pointer",
                                                     flexShrink: 0,
                                                   }}
                                                 >
                                                   ✓ Accept AI
                                                 </button>
                                               </div>
                                             );
                                           }

                                           return null;
                                         })()}
                                      </div>
                                    ) : (
                                      <div>
                                        <input
                                          type="text"
                                          className="table-input"
                                          style={{ fontSize: "11px", fontWeight: "600", color: "#1e293b", background: !(acc.approved_account_name || acc.account_name) ? "#fee2e2" : "#ffffff", border: !(acc.approved_account_name || acc.account_name) ? "2px solid #ef4444" : "1px solid var(--border-subtle)" }}
                                          value={acc.approved_account_name || acc.final_account_name || acc.account_name || acc.ai_account_name || ""}
                                          placeholder="Approved Account"
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
                                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                                    <input
                                      type="number"
                                      className="table-input"
                                      value={item.quantity ?? ""}
                                      placeholder="1"
                                      onChange={(e) => handleLineItemChange(idx, "quantity", parseFloat(e.target.value) || 0)}
                                      style={
                                        (financialValidationResult?.checks || []).some(
                                          (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && c.line_item_index === idx + 1
                                        )
                                          ? { borderColor: "#ef4444", backgroundColor: "rgba(239, 68, 68, 0.05)" }
                                          : {}
                                      }
                                    />
                                  </div>
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
                                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
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
                                      style={
                                        (financialValidationResult?.checks || []).some(
                                          (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && c.line_item_index === idx + 1
                                        )
                                          ? { borderColor: "#ef4444", backgroundColor: "rgba(239, 68, 68, 0.05)" }
                                          : {}
                                      }
                                    />
                                  </div>
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
                                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                                    <input
                                      type="number"
                                      className="table-input"
                                      value={item.taxable_amount ?? ""}
                                      placeholder="0.00"
                                      onChange={(e) => handleLineItemChange(idx, "taxable_amount", parseFloat(e.target.value) || 0)}
                                      style={
                                        (financialValidationResult?.checks || []).some(
                                          (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && c.line_item_index === idx + 1
                                        )
                                          ? { borderColor: "#ef4444", backgroundColor: "rgba(239, 68, 68, 0.05)" }
                                          : {}
                                      }
                                    />
                                    {(financialValidationResult?.checks || []).some(
                                      (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && c.line_item_index === idx + 1
                                    ) && (
                                        <span title="Line item math mismatch detected (Qty × Unit Price ≠ Taxable Amount)" style={{ position: "absolute", right: "6px", cursor: "pointer" }}>
                                          <AlertCircle size={13} style={{ color: "#ef4444" }} />
                                        </span>
                                      )}
                                  </div>
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
                      <label className="form-label" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span>Subtotal (Taxable Amount)</span>
                        {(financialValidationResult?.checks || []).some(
                          (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && (c.type === "LINE_TOTAL" || c.name?.includes("subtotal"))
                        ) && (
                            <span title="Subtotal mismatch detected" style={{ display: "inline-flex", alignItems: "center", gap: "2px", color: "#ef4444", fontSize: "11px", fontWeight: 600 }}>
                              <AlertCircle size={12} /> Math Discrepancy
                            </span>
                          )}
                      </label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.subtotal ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("subtotal", e.target.value === "" ? null : parseFloat(e.target.value))}
                        style={
                          (financialValidationResult?.checks || []).some(
                            (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && (c.type === "LINE_TOTAL" || c.name?.includes("subtotal"))
                          )
                            ? { borderColor: "#ef4444", backgroundColor: "rgba(239, 68, 68, 0.05)" }
                            : {}
                        }
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
                      <label className="form-label" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span>Total Tax Amount (Tax Total)</span>
                        {(financialValidationResult?.checks || []).some(
                          (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && (c.type === "TAX" || c.name?.includes("gst"))
                        ) && (
                            <span title="GST tax total mismatch detected" style={{ display: "inline-flex", alignItems: "center", gap: "2px", color: "#ef4444", fontSize: "11px", fontWeight: 600 }}>
                              <AlertCircle size={12} /> Tax Mismatch
                            </span>
                          )}
                      </label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.tax_total ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("tax_total", e.target.value === "" ? null : parseFloat(e.target.value))}
                        style={
                          (financialValidationResult?.checks || []).some(
                            (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && (c.type === "TAX" || c.name?.includes("gst"))
                          )
                            ? { borderColor: "#ef4444", backgroundColor: "rgba(239, 68, 68, 0.05)" }
                            : {}
                        }
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
                      <label className="form-label">Adjustment</label>
                      <input
                        type="number"
                        className="form-input"
                        value={formData.adjustment ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("adjustment", e.target.value === "" ? null : parseFloat(e.target.value))}
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
                      <label className="form-label" style={{ fontWeight: "700", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span>Total Amount (Grand Total)</span>
                        {(financialValidationResult?.checks || []).some(
                          (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && (c.type === "GRAND_TOTAL" || c.name?.includes("total"))
                        ) && (
                            <span title="Grand total equation mismatch detected" style={{ display: "inline-flex", alignItems: "center", gap: "2px", color: "#ef4444", fontSize: "11px", fontWeight: 600 }}>
                              <AlertCircle size={12} /> Math Discrepancy
                            </span>
                          )}
                      </label>
                      <input
                        type="number"
                        className="form-input"
                        style={{
                          fontSize: "16px",
                          fontWeight: "700",
                          color: (financialValidationResult?.checks || []).some(
                            (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && (c.type === "GRAND_TOTAL" || c.name?.includes("total"))
                          ) ? "#ef4444" : "var(--accent)",
                          borderColor: (financialValidationResult?.checks || []).some(
                            (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && (c.type === "GRAND_TOTAL" || c.name?.includes("total"))
                          ) ? "#ef4444" : undefined,
                          backgroundColor: (financialValidationResult?.checks || []).some(
                            (c: any) => (c.status === "MISMATCH" || c.status === "FAILED") && (c.type === "GRAND_TOTAL" || c.name?.includes("total"))
                          ) ? "rgba(239, 68, 68, 0.05)" : undefined,
                        }}
                        value={formData.total_amount ?? ""}
                        placeholder="0.00"
                        onChange={(e) => handleFieldChange("total_amount", e.target.value === "" ? null : parseFloat(e.target.value))}
                      />
                    </div>
                  </div>

                  {/* Invoice Notes / Terms */}
                  {formData.notes && (
                    <div style={{ marginTop: "12px" }}>
                      <label className="form-label">Invoice Notes</label>
                      <textarea
                        className="form-input"
                        rows={2}
                        value={formData.notes ?? ""}
                        onChange={(e) => handleFieldChange("notes", e.target.value)}
                      />
                    </div>
                  )}
                </section>

                {/* 7.5. ADDITIONAL EXTRACTED DETAILS & UNMAPPED METADATA */}
                {formData.additional_fields && Object.keys(formData.additional_fields).length > 0 && (
                  <section style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                    <details style={{ background: "#f8fafc", padding: "10px 14px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                      <summary style={{ cursor: "pointer", fontWeight: 700, fontSize: "13px", color: "#334155" }}>
                        🔍 Additional Extracted AI Metadata ({Object.keys(formData.additional_fields).length} extra fields)
                      </summary>
                      <pre style={{ marginTop: "10px", fontSize: "11px", background: "#ffffff", padding: "10px", borderRadius: "6px", border: "1px solid #cbd5e1", overflowX: "auto" }}>
                        {JSON.stringify(formData.additional_fields, null, 2)}
                      </pre>
                    </details>
                  </section>
                )}

                {/* 8. STATUTORY TDS ASSESSMENT */}
                {tdsResult && (
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
                                currTds.rate = null;
                                currTds.approved_tds_rate = null;
                                currTds.proposed_tds_amount = 0.0;
                                currTds.tds_amount = 0.0;
                              } else {
                                const secStr = String(currTds.tds_section || currTds.section || currTds.tds_provision || currTds.nature_of_payment || "").toUpperCase();
                                const rateToUse = (secStr.includes("194Q") || secStr.includes("GOODS")) ? 0.1 : (secStr.includes("194I") || secStr.includes("RENT")) ? 10.0 : 2.0;
                                currTds.tds_rate = rateToUse;
                                currTds.rate = rateToUse;
                                currTds.approved_tds_rate = rateToUse;
                                const subtotal = parseFloat(String(formData.subtotal || formData.total_amount || 0));
                                if (subtotal > 0) {
                                  currTds.tds_base_amount = subtotal;
                                  currTds.base_amount = subtotal;
                                  const calcAmt = Math.round((subtotal * rateToUse) / 100 * 100) / 100;
                                  currTds.proposed_tds_amount = calcAmt;
                                  currTds.tds_amount = calcAmt;
                                }
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
                          TDS Section
                        </label>
                        {(() => {
                          const isApp = Boolean(tdsResult.tds_applicable ?? tdsResult.applicable);
                          const secRaw = tdsResult.tds_section || tdsResult.section;
                          const provRaw = tdsResult.tds_provision || tdsResult.provision;
                          const natRaw = tdsResult.nature_of_payment;
                          const combined = `${provRaw || ""} ${secRaw || ""} ${natRaw || ""}`.toUpperCase();
                          let displaySec = secRaw || "";
                          if (isApp && (!displaySec || displaySec.includes("_"))) {
                            if (combined.includes("393") || combined.includes("194J") || combined.includes("TECHNICAL") || combined.includes("PROFESSIONAL")) displaySec = "194J / 393";
                            else if (combined.includes("194C") || combined.includes("CONTRACT")) displaySec = "194C";
                            else if (combined.includes("194I") || combined.includes("RENT")) displaySec = "194I";
                            else if (combined.includes("194H") || combined.includes("COMMISSION")) displaySec = "194H";
                            else if (combined.includes("194Q") || combined.includes("PURCHASE") || combined.includes("GOODS")) displaySec = "194Q";
                            else displaySec = "194J";
                          }
                          return (
                            <input
                              type="text"
                              placeholder="e.g. 194C, 194J, 194Q, 194I"
                              value={displaySec}
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
                          );
                        })()}
                      </div>

                      {/* TDS Statutory Provision */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Statutory Provision
                        </label>
                        {(() => {
                          const isApp = Boolean(tdsResult.tds_applicable ?? tdsResult.applicable);
                          const secRaw = tdsResult.tds_section || tdsResult.section;
                          const provRaw = tdsResult.tds_provision || tdsResult.provision;
                          const natRaw = tdsResult.nature_of_payment;
                          const combined = `${provRaw || ""} ${secRaw || ""} ${natRaw || ""}`.toUpperCase();
                          let displayProv = provRaw || "";
                          if (isApp && (!displayProv || displayProv.includes("_"))) {
                            if (combined.includes("393") || combined.includes("194J") || combined.includes("TECHNICAL") || combined.includes("PROFESSIONAL")) displayProv = "Section 194J / 393 - Fees for Technical Services";
                            else if (combined.includes("194C") || combined.includes("CONTRACT")) displayProv = "Section 194C - Payments to Contractors and Sub-contractors";
                            else if (combined.includes("194I") || combined.includes("RENT")) displayProv = "Section 194I - Rent for Property / Equipment";
                            else if (combined.includes("194H") || combined.includes("COMMISSION")) displayProv = "Section 194H - Commission or Brokerage";
                            else if (combined.includes("194Q") || combined.includes("PURCHASE") || combined.includes("GOODS")) displayProv = "Section 194Q - Purchase of Goods";
                            else displayProv = `Section ${secRaw || "194J"} - Statutory Deduction`;
                          }
                          return (
                            <input
                              type="text"
                              placeholder="e.g. Section 194J - Fees for Technical Services"
                              value={displayProv}
                              onChange={(e) => {
                                const val = e.target.value;
                                setAccountingData((prev: any) => {
                                  const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                                  currTds.tds_provision = val;
                                  currTds.provision = val;
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
                          );
                        })()}
                      </div>

                      {/* TDS Rate (%) */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Rate (%)
                        </label>
                        {(() => {
                          const isApp = Boolean(tdsResult.tds_applicable ?? tdsResult.applicable);
                          const rawRate = tdsResult.approved_tds_rate ?? tdsResult.tds_rate ?? tdsResult.rate;
                          const secStr = String(tdsResult.tds_section || tdsResult.tds_provision || tdsResult.nature_of_payment || "").toUpperCase();
                          const fallbackRate = (secStr.includes("194Q") || secStr.includes("GOODS")) ? 0.1 : (secStr.includes("194I") || secStr.includes("RENT")) ? 10.0 : 2.0;
                          const displayRate = isApp
                            ? (rawRate !== null && rawRate !== undefined && parseFloat(String(rawRate)) > 0
                                ? rawRate
                                : fallbackRate)
                            : (rawRate !== null && rawRate !== undefined ? rawRate : "");
                          return (
                            <input
                              type="number"
                              step="0.01"
                              placeholder="e.g. 0.1, 1, 2, 10"
                              value={displayRate !== null && displayRate !== undefined ? displayRate : ""}
                              onChange={(e) => {
                                const val = e.target.value === "" ? null : parseFloat(e.target.value);
                                setAccountingData((prev: any) => {
                                  const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                                  currTds.tds_rate = val;
                                  currTds.rate = val;
                                  currTds.approved_tds_rate = val;
                                  const subtotal = parseFloat(String(currTds.tds_base_amount || currTds.base_amount || formData.subtotal || formData.total_amount || 0));
                                  if (val !== null && subtotal > 0) {
                                    const calcAmt = Math.round((subtotal * val) / 100 * 100) / 100;
                                    currTds.proposed_tds_amount = calcAmt;
                                    currTds.tds_amount = calcAmt;
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
                          );
                        })()}
                      </div>

                      {/* TDS Base Amount */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Base Amount (₹)
                        </label>
                        {(() => {
                          const isApp = Boolean(tdsResult.tds_applicable ?? tdsResult.applicable);
                          const rawBase = tdsResult.tds_base_amount ?? tdsResult.base_amount;
                          const displayBase = isApp
                            ? (rawBase !== null && rawBase !== undefined && parseFloat(String(rawBase)) > 0
                                ? rawBase
                                : (formData.subtotal || (formData as any).taxable_amount || formData.total_amount || ""))
                            : (rawBase !== null && rawBase !== undefined ? rawBase : "");
                          return (
                            <input
                              type="number"
                              step="0.01"
                              placeholder="e.g. 50000.00"
                              value={displayBase !== null && displayBase !== undefined ? displayBase : ""}
                              onChange={(e) => {
                                const val = e.target.value === "" ? null : parseFloat(e.target.value);
                                setAccountingData((prev: any) => {
                                  const currTds = { ...(prev.tds_assessment || prev.tds || {}) };
                                  currTds.tds_base_amount = val;
                                  currTds.base_amount = val;
                                  const rate = parseFloat(String(currTds.approved_tds_rate ?? currTds.tds_rate ?? currTds.rate ?? "0")) || 0;
                                  if (val !== null && rate > 0) {
                                    const calcAmt = Math.round((val * rate) / 100 * 100) / 100;
                                    currTds.proposed_tds_amount = calcAmt;
                                    currTds.tds_amount = calcAmt;
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
                          );
                        })()}
                      </div>

                      {/* Proposed TDS Amount */}
                      <div>
                        <label style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>
                          TDS Withholding Amount (₹)
                        </label>
                        {(() => {
                          const isApp = Boolean(tdsResult.tds_applicable ?? tdsResult.applicable);
                          const rawAmt = tdsResult.proposed_tds_amount ?? tdsResult.tds_amount;
                          const rawRate = parseFloat(String(tdsResult.approved_tds_rate ?? tdsResult.tds_rate ?? tdsResult.rate ?? "0"));
                          const secStr = String(tdsResult.tds_section || tdsResult.tds_provision || tdsResult.nature_of_payment || "").toUpperCase();
                          const fallbackRate = (secStr.includes("194Q") || secStr.includes("GOODS")) ? 0.1 : (secStr.includes("194I") || secStr.includes("RENT")) ? 10.0 : 2.0;
                          const effectiveRate = rawRate > 0 ? rawRate : fallbackRate;
                          const baseVal = (tdsResult.tds_base_amount ?? tdsResult.base_amount) || (formData.subtotal || (formData as any).taxable_amount || formData.total_amount || 0);
                          const rawBase = parseFloat(String(baseVal || "0"));
                          const computedAmt = (rawBase > 0 && effectiveRate > 0) ? Math.round((rawBase * effectiveRate) / 100 * 100) / 100 : 0;
                          const displayAmt = isApp
                            ? (rawAmt !== null && rawAmt !== undefined && parseFloat(String(rawAmt)) > 0
                                ? rawAmt
                                : computedAmt)
                            : 0;
                          return (
                            <input
                              type="number"
                              step="0.01"
                              placeholder="0.00"
                              value={displayAmt !== null && displayAmt !== undefined ? displayAmt : ""}
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
                          );
                        })()}
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
                        className={`badge ${(gstResult?.supply_type === "INTRA_STATE" || (!gstResult && (formData.cgst_amount || formData.cgst || formData.sgst_amount || formData.sgst)))
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
                          className={`badge ${gstResult.validation_status === "PASSED"
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
                    {itcResult && (
                      <span
                        className={`badge ${itcResult.status === "ELIGIBLE"
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
                    )}
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
                          className={`badge ${(journalEntry.validation?.balanced ?? (journalEntry.difference === 0 && journalEntry.total_debit > 0))
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
                          className={`badge ${journalEntry.status === "APPROVED" || journalEntry.approval_status === "APPROVED"
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
                          {journalEntry.lines?.map((line, idx) => {
                            const isUncertain = isUncertainCoaLine(line);
                            const isTaxLine = line.line_type === "INPUT_TAX";
                            const isApLine = line.line_type === "ACCOUNTS_PAYABLE";

                            let selAccValue = "";
                            if (zohoAccounts && zohoAccounts.length > 0) {
                              const cleanLineAccName = String(line.account_name || "").replace(/^\[Unapproved\]\s*/i, "").trim();
                              const accIdStr = String(line.account_id || "").trim();
                              const lineTypeStr = String(line.line_type || "").toUpperCase();

                              const matchedZohoAcc = zohoAccounts.find(
                                (za: any) =>
                                  String(za.zoho_account_id) === accIdStr ||
                                  za.account_name.toLowerCase().trim() === cleanLineAccName.toLowerCase()
                              );

                              if (matchedZohoAcc) {
                                selAccValue = String(matchedZohoAcc.zoho_account_id);
                              } else if (isTaxLine || accIdStr.startsWith("TAX_") || cleanLineAccName.toLowerCase().includes("tax")) {
                                let taxMatch = null;
                                if (cleanLineAccName.toLowerCase().includes("igst") || accIdStr.includes("IGST")) {
                                  taxMatch = zohoAccounts.find((za: any) => za.account_name.toLowerCase().includes("input igst"));
                                } else if (cleanLineAccName.toLowerCase().includes("cgst") || accIdStr.includes("CGST")) {
                                  taxMatch = zohoAccounts.find((za: any) => za.account_name.toLowerCase().includes("input cgst"));
                                } else if (cleanLineAccName.toLowerCase().includes("sgst") || accIdStr.includes("SGST")) {
                                  taxMatch = zohoAccounts.find((za: any) => za.account_name.toLowerCase().includes("input sgst"));
                                }
                                if (!taxMatch) {
                                  taxMatch = zohoAccounts.find(
                                    (za: any) =>
                                      (za.account_type || "").toLowerCase().includes("tax") ||
                                      (za.account_name || "").toLowerCase().includes("input tax") ||
                                      (za.account_name || "").toLowerCase().includes("tax credit")
                                  );
                                }
                                if (taxMatch) selAccValue = String(taxMatch.zoho_account_id);
                              } else if (isApLine || accIdStr.startsWith("LIAB_") || cleanLineAccName.toLowerCase().includes("payable")) {
                                const apMatch = zohoAccounts.find(
                                  (za: any) =>
                                    za.account_type === "accounts_payable" ||
                                    za.account_name.toLowerCase().includes("accounts payable")
                                );
                                if (apMatch) selAccValue = String(apMatch.zoho_account_id);
                              }
                            }

                            return (
                              <tr
                                key={idx}
                                style={{
                                  borderBottom: "1px solid var(--border-subtle)",
                                  background: isUncertain ? "rgba(254, 242, 242, 0.4)" : "transparent",
                                }}
                              >
                                <td style={{ padding: "6px", color: "var(--text-secondary)" }}>{idx + 1}</td>
                                <td style={{ padding: "6px" }}>
                                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                    {zohoAccounts && zohoAccounts.length > 0 ? (
                                      <select
                                        className="table-input"
                                        style={{
                                          background: isUncertain ? "#fef2f2" : "#ffffff",
                                          border: isUncertain ? "1.5px solid #ef4444" : "1px solid var(--border-subtle)",
                                          borderRadius: "var(--radius-sm)",
                                          padding: "4px 6px",
                                          width: "100%",
                                          fontSize: "11px",
                                          fontWeight: isUncertain ? "600" : "500",
                                          color: isUncertain ? "#991b1b" : "var(--text-primary)",
                                          boxShadow: isUncertain ? "0 0 0 1px rgba(239, 68, 68, 0.15)" : "none",
                                        }}
                                        value={selAccValue}
                                        onChange={(e) => {
                                          const selId = e.target.value;
                                          const match = zohoAccounts.find((za: any) => String(za.zoho_account_id) === String(selId));
                                          const selName = match ? match.account_name : selId;
                                          handleJournalLineChange(idx, "account_id", selId);
                                          handleJournalLineChange(idx, "account_name", selName);
                                          handleJournalLineChange(idx, "match_status", "EXACT_MATCH");
                                          handleJournalLineChange(idx, "ai_needs_review", false);
                                          handleJournalLineChange(idx, "provenance", "HUMAN_APPROVED");
                                        }}
                                      >
                                        <option value="">-- Select Account --</option>
                                        {!zohoAccounts.some((za: any) => String(za.zoho_account_id) === String(selAccValue)) && Boolean(selAccValue) && (
                                          <option value={selAccValue}>{line.account_name || selAccValue}</option>
                                        )}
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
                                        style={{
                                          fontSize: "11px",
                                          fontWeight: "600",
                                          border: isUncertain ? "1.5px solid #ef4444" : "1px solid var(--border-subtle)",
                                          background: isUncertain ? "#fef2f2" : "#ffffff",
                                          color: isUncertain ? "#991b1b" : "var(--text-primary)",
                                        }}
                                        value={line.account_name ?? ""}
                                        placeholder="Account Name"
                                        onChange={(e) => {
                                          handleJournalLineChange(idx, "account_name", e.target.value);
                                          handleJournalLineChange(idx, "match_status", "EXACT_MATCH");
                                          handleJournalLineChange(idx, "ai_needs_review", false);
                                          handleJournalLineChange(idx, "provenance", "HUMAN_APPROVED");
                                        }}
                                      />
                                    )}

                                    {/* Interactive Badge to open COA Review Modal */}
                                    <div>
                                      {isUncertain ? (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setReviewCoaModalLineIdx(idx);
                                            setModalSelectedAccountId(selAccValue);
                                            setShowReviewCoaModal(true);
                                          }}
                                          style={{
                                            padding: "2px 6px",
                                            fontSize: "10px",
                                            fontWeight: "600",
                                            color: "#dc2626",
                                            background: "#fee2e2",
                                            border: "1px solid #fca5a5",
                                            borderRadius: "4px",
                                            cursor: "pointer",
                                            display: "inline-flex",
                                            alignItems: "center",
                                            gap: "4px",
                                          }}
                                          title="Uncertain or unverified COA - Click to open review & approval popup"
                                        >
                                          <AlertTriangle size={11} />
                                          ⚠️ Review COA (Detected)
                                        </button>
                                      ) : (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setReviewCoaModalLineIdx(idx);
                                            setModalSelectedAccountId(selAccValue);
                                            setShowReviewCoaModal(true);
                                          }}
                                          style={{
                                            padding: "1px 5px",
                                            fontSize: "9px",
                                            fontWeight: "500",
                                            color: "#059669",
                                            background: "#ecfdf5",
                                            border: "1px solid #a7f3d0",
                                            borderRadius: "4px",
                                            cursor: "pointer",
                                            display: "inline-flex",
                                            alignItems: "center",
                                            gap: "3px",
                                          }}
                                          title="COA Verified - Click to edit or review detection details"
                                        >
                                          <CheckCircle2 size={10} />
                                          ✓ COA Verified (Review / Edit)
                                        </button>
                                      )}
                                    </div>
                                  </div>
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
                                    background: line.provenance === "HITL_OVERRIDE" || line.provenance === "CUSTOMER_EDIT" || line.provenance === "MANUAL_EDIT" ? "#fef3c7" : "#f1f5f9",
                                    color: line.provenance === "HITL_OVERRIDE" || line.provenance === "CUSTOMER_EDIT" || line.provenance === "MANUAL_EDIT" ? "#92400e" : "var(--text-secondary)",
                                    fontWeight: "600",
                                    fontSize: "9px",
                                  }}
                                >
                                  {line.provenance === "HITL_OVERRIDE" ? "EDITED" : (line.provenance || "EDITED")}
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
                          );
                        })}
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

      {/* ==================================================== */}
      {/* REAL REACT MODAL FOR CREATING COA IN ZOHO BOOKS       */}
      {/* ==================================================== */}
      {showCreateCoaModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
        >
          <div
            className="card"
            style={{
              width: "480px",
              maxWidth: "92vw",
              backgroundColor: "#ffffff",
              borderRadius: "12px",
              padding: "24px",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Plus size={18} style={{ color: "#2563eb" }} />
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#0f172a" }}>Create New Chart of Account in Zoho</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowCreateCoaModal(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#64748b" }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Account Name <span style={{ color: "#ef4444" }}>*</span>
                </label>
                <input
                  type="text"
                  className="table-input"
                  style={{ width: "100%", padding: "8px 10px", fontSize: "13px" }}
                  value={createCoaFormData.account_name}
                  onChange={(e) => setCreateCoaFormData({ ...createCoaFormData, account_name: e.target.value })}
                  placeholder="e.g. Office Expenses"
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Account Type <span style={{ color: "#ef4444" }}>*</span>
                </label>
                <select
                  className="table-input"
                  style={{ width: "100%", padding: "8px 10px", fontSize: "13px" }}
                  value={createCoaFormData.account_type}
                  onChange={(e) => setCreateCoaFormData({ ...createCoaFormData, account_type: e.target.value })}
                >
                  <option value="expense">Expense</option>
                  <option value="cost_of_goods_sold">Cost of Goods Sold</option>
                  <option value="fixed_asset">Fixed Asset</option>
                  <option value="other_current_asset">Other Current Asset</option>
                  <option value="other_current_liability">Other Current Liability</option>
                  <option value="other_expense">Other Expense</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Account Code (Optional)
                </label>
                <input
                  type="text"
                  className="table-input"
                  style={{ width: "100%", padding: "8px 10px", fontSize: "13px" }}
                  value={createCoaFormData.account_code}
                  onChange={(e) => setCreateCoaFormData({ ...createCoaFormData, account_code: e.target.value })}
                  placeholder="e.g. 5010"
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Description (Optional)
                </label>
                <textarea
                  className="table-input"
                  rows={2}
                  style={{ width: "100%", padding: "8px 10px", fontSize: "13px", resize: "none" }}
                  value={createCoaFormData.description}
                  onChange={(e) => setCreateCoaFormData({ ...createCoaFormData, description: e.target.value })}
                  placeholder="Account description..."
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
              <button
                type="button"
                onClick={() => setShowCreateCoaModal(false)}
                className="btn btn-secondary"
                disabled={isCreatingCoa}
                style={{ padding: "8px 16px", fontSize: "13px" }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isCreatingCoa || !createCoaFormData.account_name.trim()}
                onClick={async () => {
                  try {
                    setIsCreatingCoa(true);
                    const { createZohoCOA, assignInvoiceCOA } = await import("@/lib/api");
                    const created = await createZohoCOA({
                      account_name: createCoaFormData.account_name.trim(),
                      account_type: createCoaFormData.account_type,
                      account_code: createCoaFormData.account_code.trim() || undefined,
                      description: createCoaFormData.description.trim() || undefined,
                    });
                    const newId = created.chart_of_account?.zoho_account_id;
                    if (!newId) throw new Error("No Zoho Account ID returned from server.");
                    const res = await assignInvoiceCOA(invoiceId, {
                      zoho_account_id: newId,
                      account_name: created.chart_of_account?.account_name || createCoaFormData.account_name,
                      account_type: createCoaFormData.account_type,
                      account_code: createCoaFormData.account_code || undefined,
                    });
                    setInvoice(res);
                    if (res.current_accounting_output) setAccountingData(res.current_accounting_output);
                    getZohoMasterData().then((m) => setZohoAccounts(m.accounts || [])).catch(() => null);
                    setShowCreateCoaModal(false);
                    setActionNotice(`✓ Created & persisted new Zoho COA '${createCoaFormData.account_name}'!`);
                    setTimeout(() => setActionNotice(null), 4000);
                  } catch (err: any) {
                    setError(err.message || "Failed to create/assign COA.");
                  } finally {
                    setIsCreatingCoa(false);
                  }
                }}
                className="btn btn-primary"
                style={{ padding: "8px 18px", fontSize: "13px" }}
              >
                {isCreatingCoa ? "Creating in Zoho..." : "Create COA"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* REAL REACT MODAL FOR MATHEMATICAL DISCREPANCY DETAILS */}
      {/* ==================================================== */}
      {showMathDiscrepancyModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
        >
          <div
            className="card"
            style={{
              width: "720px",
              maxWidth: "92vw",
              maxHeight: "85vh",
              overflowY: "auto",
              backgroundColor: "#ffffff",
              borderRadius: "12px",
              padding: "24px",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <AlertCircle size={18} style={{ color: "#ef4444" }} />
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#0f172a" }}>Mathematical Discrepancy Breakdown</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowMathDiscrepancyModal(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#64748b" }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "16px", lineHeight: "1.5" }}>
              Extracted invoice values do not mathematically reconcile. Please review the comparison below against the original invoice document.
            </p>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse", color: "var(--text-primary)" }}>
                <thead>
                  <tr style={{ background: "rgba(239, 68, 68, 0.1)", textAlign: "left", borderBottom: "1px solid rgba(239, 68, 68, 0.2)" }}>
                    <th style={{ padding: "8px 10px" }}>Check Type</th>
                    <th style={{ padding: "8px 10px" }}>Field / Location</th>
                    <th style={{ padding: "8px 10px" }}>Extracted</th>
                    <th style={{ padding: "8px 10px" }}>Calculated</th>
                    <th style={{ padding: "8px 10px" }}>Difference</th>
                    <th style={{ padding: "8px 10px" }}>Explanation</th>
                  </tr>
                </thead>
                <tbody>
                  {(financialValidationResult?.checks || []).map((chk: any, cIdx: number) => {
                    if (chk.status !== "MISMATCH" && chk.status !== "FAILED") return null;
                    return (
                      <tr key={cIdx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "8px 10px", fontWeight: "600", color: "#ef4444" }}>{chk.type || chk.name || "CHECK"}</td>
                        <td style={{ padding: "8px 10px" }}>{chk.field || "Header/Line"}</td>
                        <td style={{ padding: "8px 10px" }}>₹{Number(chk.invoice_value ?? chk.source_value ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                        <td style={{ padding: "8px 10px" }}>₹{Number(chk.calculated_value ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                        <td style={{ padding: "8px 10px", fontWeight: "700", color: "#ef4444" }}>₹{Number(chk.difference ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                        <td style={{ padding: "8px 10px", fontSize: "11px", color: "var(--text-secondary)" }}>{chk.message || chk.note || "Calculated equation does not reconcile with extracted value."}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "20px" }}>
              <button
                type="button"
                onClick={() => setShowMathDiscrepancyModal(false)}
                className="btn btn-secondary"
                style={{ padding: "8px 18px", fontSize: "13px" }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* REAL REACT MODAL FOR COA DETECTION & APPROVAL        */}
      {/* ==================================================== */}
      {showReviewCoaModal && reviewCoaModalLineIdx !== null && journalEntry?.lines?.[reviewCoaModalLineIdx] && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
        >
          {(() => {
            const lineIdx = reviewCoaModalLineIdx;
            const targetLine = journalEntry.lines[lineIdx];
            const isUncertain = isUncertainCoaLine(targetLine);
            const currentAccName = targetLine.account_name || "Unassigned";
            const currentAccCode = targetLine.account_id || "N/A";
            const currentMatchStatus = targetLine.match_status || (isUncertain ? "NEEDS_REVIEW" : "EXACT_MATCH");

            return (
              <div
                className="card"
                style={{
                  width: "540px",
                  maxWidth: "92vw",
                  backgroundColor: "#ffffff",
                  borderRadius: "12px",
                  padding: "24px",
                  boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <BookOpen size={20} style={{ color: isUncertain ? "#dc2626" : "#059669" }} />
                    <div>
                      <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#0f172a" }}>
                        COA Detection & Verification
                      </h3>
                      <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                        Journal Line #{lineIdx + 1} ({targetLine.line_type || "EXPENSE"})
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowReviewCoaModal(false)}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "#64748b" }}
                  >
                    <X size={18} />
                  </button>
                </div>

                {/* AI Detection Info Card */}
                <div
                  style={{
                    backgroundColor: isUncertain ? "#fef2f2" : "#f0fdf4",
                    border: isUncertain ? "1px solid #fecaca" : "1px solid #bbf7d0",
                    borderRadius: "8px",
                    padding: "14px",
                    marginBottom: "16px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <div style={{ fontSize: "12px", fontWeight: "700", color: isUncertain ? "#991b1b" : "#166534" }}>
                      AI Detected Account Classification
                    </div>
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: "700",
                        padding: "2px 8px",
                        borderRadius: "12px",
                        backgroundColor: isUncertain ? "#fee2e2" : "#dcfce7",
                        color: isUncertain ? "#b91c1c" : "#15803d",
                      }}
                    >
                      {currentMatchStatus}
                    </span>
                  </div>
                  <div style={{ fontSize: "13px", fontWeight: "600", color: "#0f172a", marginBottom: "4px" }}>
                    {currentAccName} {currentAccCode ? `(${currentAccCode})` : ""}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-secondary)", lineHeight: "1.4" }}>
                    {targetLine.description ? `Description: "${targetLine.description}"` : `Line Item #${targetLine.source_line_index || lineIdx + 1}`}
                  </div>
                  <div style={{ fontSize: "11px", color: isUncertain ? "#b91c1c" : "#15803d", marginTop: "8px", fontStyle: "italic" }}>
                    {isUncertain
                      ? "⚠️ Warning: This COA detection is unverified or uncertain. Please review or select the correct account below."
                      : "✓ This COA classification is verified and matches your Chart of Accounts."}
                  </div>
                </div>

                {/* Account Selection Form */}
                <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "20px" }}>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#334155" }}>
                    Select Chart of Account (Zoho Books)
                  </label>
                  {zohoAccounts && zohoAccounts.length > 0 ? (
                    <select
                      className="table-input"
                      style={{ width: "100%", padding: "10px", fontSize: "13px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}
                      value={modalSelectedAccountId}
                      onChange={(e) => setModalSelectedAccountId(e.target.value)}
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
                      style={{ width: "100%", padding: "10px", fontSize: "13px", borderRadius: "6px" }}
                      value={modalSelectedAccountId}
                      onChange={(e) => setModalSelectedAccountId(e.target.value)}
                      placeholder="Account Name / Code"
                    />
                  )}

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <button
                      type="button"
                      onClick={() => {
                        setShowReviewCoaModal(false);
                        setShowCreateCoaModal(true);
                      }}
                      style={{ background: "none", border: "none", color: "#2563eb", fontSize: "11px", fontWeight: "600", cursor: "pointer", padding: 0 }}
                    >
                      + Create New COA in Zoho Books
                    </button>
                  </div>
                </div>

                {/* Modal Buttons */}
                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                  <button
                    type="button"
                    onClick={() => setShowReviewCoaModal(false)}
                    className="btn btn-secondary"
                    style={{ padding: "8px 16px", fontSize: "13px" }}
                  >
                    Cancel
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      // Apply COA & Approve Line
                      let finalId = modalSelectedAccountId;
                      let finalName = currentAccName;

                      if (zohoAccounts && zohoAccounts.length > 0) {
                        const match = zohoAccounts.find((za: any) => String(za.zoho_account_id) === String(finalId));
                        if (match) {
                          finalName = match.account_name;
                        } else if (!finalId) {
                          // Default to first zoho account if unselected
                          finalId = zohoAccounts[0].zoho_account_id;
                          finalName = zohoAccounts[0].account_name;
                        }
                      }

                      handleJournalLineChange(lineIdx, "account_id", finalId);
                      handleJournalLineChange(lineIdx, "account_name", finalName.replace(" [Unapproved]", ""));
                      handleJournalLineChange(lineIdx, "match_status", "EXACT_MATCH");
                      handleJournalLineChange(lineIdx, "ai_needs_review", false);
                      handleJournalLineChange(lineIdx, "provenance", "HUMAN_APPROVED");

                      setShowReviewCoaModal(false);
                      setActionNotice(`✓ Approved COA '${finalName}' for line #${lineIdx + 1}!`);
                      setTimeout(() => setActionNotice(null), 3000);
                    }}
                    className="btn btn-primary"
                    style={{
                      padding: "8px 18px",
                      fontSize: "13px",
                      background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
                      color: "#ffffff",
                    }}
                  >
                    ✓ Approve & Confirm COA
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
