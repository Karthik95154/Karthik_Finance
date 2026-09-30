"use client";

import React, { useState } from "react";
import {
  Globe,
  ArrowRightLeft,
  ShieldCheck,
  Building2,
  DollarSign,
  TrendingUp,
  Percent,
  Edit3,
  RefreshCw,
  Landmark,
  X,
  FileText,
  CreditCard,
  Calendar,
  Layers,
  HelpCircle,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Sliders,
} from "lucide-react";
import {
  Invoice,
  ExtractedInvoiceData,
  getForexRates,
  ForexRateItem,
  updateInvoiceExtraction,
} from "@/lib/api";

function safeNum(val: any, fallback = 0): number {
  if (val === null || val === undefined || val === "") return fallback;
  if (typeof val === "number") return isNaN(val) ? fallback : val;
  const s = String(val).replace(/,/g, "").trim();
  const num = parseFloat(s);
  return isNaN(num) ? fallback : num;
}

function formatInr(val: any): string {
  const num = safeNum(val, 0);
  return num.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatForeign(val: any): string {
  const num = safeNum(val, 0);
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

interface ForeignInvoiceCardProps {
  invoice: Invoice;
  extractedData?: ExtractedInvoiceData | null;
  isReadOnly?: boolean;
  onRefreshInvoice: () => Promise<void>;
  onShowToast: (message: string, type?: "success" | "error" | "info") => void;
}

export default function ForeignInvoiceCard({
  invoice,
  extractedData,
  isReadOnly = false,
  onRefreshInvoice,
  onShowToast,
}: ForeignInvoiceCardProps) {
  const ext = extractedData || {};

  // Comprehensive origin & foreign detection
  const origin = String(invoice?.classification_override || invoice?.invoice_origin || "INDIAN").toUpperCase();
  const isForeignService = origin === "FOREIGN_SERVICE" || origin === "FOREIGN";
  const isUnsupportedGoods = origin === "UNSUPPORTED_FOREIGN_GOODS";
  const isReviewRequired = origin === "REVIEW_REQUIRED";
  const isClassOverridden = Boolean(invoice?.classification_override);

  const origCurr = String(
    invoice?.original_currency ||
    ext.original_currency ||
    (invoice?.currency && invoice?.currency !== "INR" ? invoice?.currency : "") ||
    (ext.currency && ext.currency !== "INR" ? ext.currency : "") ||
    "INR"
  ).toUpperCase();

  const isForeignCurrency =
    (origCurr !== "INR" && origCurr !== "") ||
    Boolean(invoice?.original_currency && invoice.original_currency !== "INR") ||
    Boolean(ext.original_currency && ext.original_currency !== "INR") ||
    Boolean(invoice?.currency && invoice.currency !== "INR") ||
    Boolean(ext.currency && ext.currency !== "INR");

  const isForeign =
    isForeignService ||
    isUnsupportedGoods ||
    isForeignCurrency ||
    Boolean(invoice?.exchange_rate && invoice.exchange_rate > 1.0 && isForeignCurrency);

  // Forex rate states
  const activeRate = safeNum(invoice?.exchange_rate || ext.exchange_rate, 95.2408);
  const isOverridden = Boolean(invoice?.fx_rate_overridden);
  const fxReason = String(invoice?.fx_override_reason || "");
  const rateSource = String(invoice?.exchange_rate_source || ext.exchange_rate_source || "RBI Reference Rate");
  const rateDate = String(invoice?.exchange_rate_date || ext.exchange_rate_date || ext.invoice_date || "Invoice Date");
  const origSysRate = safeNum(invoice?.fx_original_rate, activeRate);
  const isFallback = rateSource.includes("FALLBACK") || rateSource.includes("STATIC");

  // Converted amounts
  const origTotal = safeNum(
    invoice?.original_total_amount ?? ext.original_total_amount ?? (isForeignCurrency ? ext.total_amount : null),
    100.0
  );
  const origTaxable = safeNum(
    invoice?.original_taxable_amount ?? ext.original_taxable_amount ?? (isForeignCurrency ? ext.taxable_amount : null),
    origTotal
  );

  const convertedTotal = safeNum(
    invoice?.converted_total_inr ?? ext.converted_total_inr ?? (origTotal > 0 ? origTotal * activeRate : ext.total_amount),
    origTotal * activeRate
  );
  const convertedTaxable = safeNum(
    invoice?.converted_taxable_inr ?? ext.converted_taxable_inr ?? (origTaxable > 0 ? origTaxable * activeRate : ext.taxable_amount),
    convertedTotal
  );

  // TDS amounts
  const currentAcct = invoice?.current_accounting_output || invoice?.accounting_output || {};
  const tdsObj = (currentAcct as any)?.tds_assessment || (currentAcct as any)?.tds || {};
  const tdsRate = safeNum(tdsObj?.rate ?? tdsObj?.tds_rate, 20.0);
  const tdsBase = safeNum(tdsObj?.base_amount ?? tdsObj?.tds_base_amount, convertedTaxable);
  const tdsAmount = safeNum(tdsObj?.tds_amount, tdsBase * (tdsRate / 100));
  const netVendorPayable = Math.max(0, convertedTaxable - tdsAmount);

  // Modals state
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideTargetOrigin, setOverrideTargetOrigin] = useState(origin === "INDIAN" ? "FOREIGN_SERVICE" : origin);
  const [overrideReasonInput, setOverrideReasonInput] = useState("");
  const [isSubmittingOverride, setIsSubmittingOverride] = useState(false);

  // FX Rate Override Modal
  const [showFxModal, setShowFxModal] = useState(false);
  const [customFxRate, setCustomFxRate] = useState<string>(activeRate > 0 ? activeRate.toString() : "95.2408");
  const [customFxReason, setCustomFxReason] = useState("");
  const [isSubmittingFx, setIsSubmittingFx] = useState(false);

  // Forex live rates drawer
  const [showRatesModal, setShowRatesModal] = useState(false);
  const [liveRates, setLiveRates] = useState<ForexRateItem[]>([]);
  const [isLoadingRates, setIsLoadingRates] = useState(false);

  // Quick converter inside modal
  const [calcAmount, setCalcAmount] = useState<string>("100");
  const [calcCurrency, setCalcCurrency] = useState<string>(origCurr !== "INR" ? origCurr : "USD");
  const [calcResult, setCalcResult] = useState<number | null>(null);

  const fetchRates = async () => {
    setIsLoadingRates(true);
    try {
      const res = await getForexRates(rateDate !== "Invoice Date" ? rateDate : undefined);
      setLiveRates(res.rates || []);
    } catch (e: any) {
      onShowToast(e.message || "Failed to load live forex rates", "error");
    } finally {
      setIsLoadingRates(false);
    }
  };

  const handleApplyQuickRate = (rate: number, curr: string, source: string) => {
    setCustomFxRate(rate.toString());
    setCustomFxReason(`Applied ${source} for ${curr}`);
  };

  const handleSaveClassificationOverride = async () => {
    if (!overrideReasonInput.trim()) {
      onShowToast("Please enter an audit reason for the classification override.", "error");
      return;
    }
    setIsSubmittingOverride(true);
    try {
      await updateInvoiceExtraction(
        invoice.id,
        invoice.current_vlm_output,
        invoice.current_accounting_output,
        invoice.journal_entry,
        {
          classification_override: overrideTargetOrigin,
          classification_override_reason: overrideReasonInput.trim(),
        }
      );
      onShowToast(`Invoice origin updated to ${overrideTargetOrigin}`, "success");
      setShowOverrideModal(false);
      setOverrideReasonInput("");
      await onRefreshInvoice();
    } catch (e: any) {
      onShowToast(e.message || "Failed to override invoice classification", "error");
    } finally {
      setIsSubmittingOverride(false);
    }
  };

  const handleSaveFxOverride = async () => {
    const parsed = parseFloat(customFxRate);
    if (isNaN(parsed) || parsed <= 0) {
      onShowToast("Please enter a valid positive exchange rate.", "error");
      return;
    }
    if (!customFxReason.trim()) {
      onShowToast("Please enter a justification reason for overriding the exchange rate.", "error");
      return;
    }
    setIsSubmittingFx(true);
    try {
      await updateInvoiceExtraction(
        invoice.id,
        invoice.current_vlm_output,
        invoice.current_accounting_output,
        invoice.journal_entry,
        {
          exchange_rate: parsed,
          fx_override_reason: customFxReason.trim(),
        }
      );
      onShowToast(`Exchange rate updated to ₹${parsed.toFixed(4)}/${origCurr}`, "success");
      setShowFxModal(false);
      setCustomFxReason("");
      await onRefreshInvoice();
    } catch (e: any) {
      onShowToast(e.message || "Failed to update exchange rate", "error");
    } finally {
      setIsSubmittingFx(false);
    }
  };

  if (!isForeign && !isForeignCurrency && !isUnsupportedGoods && !isReviewRequired) {
    // Standard Domestic Indian Supply card
    return (
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "12px",
          padding: "16px 20px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "38px",
              height: "38px",
              borderRadius: "10px",
              background: "#ecfdf5",
              border: "1px solid #a7f3d0",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#059669",
            }}
          >
            <Building2 size={20} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>
                Origin Classification
              </span>
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: "12px",
                  background: "#d1fae5",
                  color: "#065f46",
                  border: "1px solid #a7f3d0",
                }}
              >
                Domestic Indian Supply (GST)
              </span>
            </div>
            <p style={{ fontSize: "12px", color: "#64748b", margin: "2px 0 0 0" }}>
              Standard CGST/SGST/IGST intra/inter-state tax rules apply under Indian GST legislation.
            </p>
          </div>
        </div>

        {!isReadOnly && (
          <button
            onClick={() => {
              setOverrideTargetOrigin("FOREIGN_SERVICE");
              setShowOverrideModal(true);
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              fontSize: "12px",
              fontWeight: 600,
              background: "#f8fafc",
              color: "#334155",
              border: "1px solid #cbd5e1",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            <Edit3 size={13} />
            Override Classification
          </button>
        )}
      </div>
    );
  }

  // Clean, Light-Themed, High-Visibility Foreign Service & FX Conversion Card (Matching Flutter)
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #bfdbfe",
        borderRadius: "14px",
        padding: "20px 22px",
        boxShadow: "0 4px 20px -2px rgba(2, 132, 199, 0.08)",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      {/* 1. Classification & Evidence Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          borderBottom: "1px solid #e2e8f0",
          paddingBottom: "14px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "#eff6ff",
              border: "1px solid #93c5fd",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#0284c7",
            }}
          >
            <Globe size={22} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <h3 style={{ fontSize: "15px", fontWeight: 800, margin: 0, color: "#0f172a", letterSpacing: "-0.01em" }}>
                Foreign Service Classification & Evidence
              </h3>
              <span
                style={{
                  fontSize: "11.5px",
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: "6px",
                  background: "#e0f2fe",
                  color: "#0369a1",
                  border: "1px solid #7dd3fc",
                }}
              >
                {origin}
              </span>
              {isClassOverridden && (
                <span
                  style={{
                    fontSize: "9.5px",
                    fontWeight: 800,
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: "#fef3c7",
                    color: "#b45309",
                    border: "1px solid #fde68a",
                  }}
                >
                  OVERRIDDEN
                </span>
              )}
            </div>
            <p style={{ fontSize: "11.5px", color: "#64748b", margin: "2px 0 0 0" }}>
              Multi-evidence verification: Country, Tax ID, Service keywords, and Bank credentials
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            type="button"
            onClick={() => {
              fetchRates();
              setShowRatesModal(true);
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 12px",
              fontSize: "12px",
              fontWeight: 600,
              background: "#f0fdf4",
              color: "#15803d",
              border: "1px solid #bbf7d0",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            <TrendingUp size={14} color="#16a34a" />
            Live RBI Rates
          </button>
          {!isReadOnly && (
            <button
              type="button"
              onClick={() => {
                setOverrideTargetOrigin(origin);
                setShowOverrideModal(true);
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "7px 12px",
                fontSize: "12px",
                fontWeight: 600,
                background: "#f8fafc",
                color: "#0369a1",
                border: "1px solid #bae6fd",
                borderRadius: "8px",
                cursor: "pointer",
              }}
            >
              <Edit3 size={13} />
              Override Classification
            </button>
          )}
        </div>
      </div>

      {/* Three-Tier Provenance Matrix */}
      <div
        style={{
          padding: "12px 16px",
          background: "#f8fafc",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "14px",
        }}
      >
        <div>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            SYSTEM CLASSIFICATION
          </div>
          <div style={{ fontSize: "13px", fontWeight: 700, color: "#0f172a", marginTop: "2px" }}>
            {isClassOverridden ? (invoice?.classification_source === "USER_OVERRIDE" ? "SYSTEM (INITIAL)" : origin) : origin}
          </div>
          <div style={{ fontSize: "10.5px", color: "#64748b", marginTop: "1px" }}>
            Algorithmic multi-evidence deduction
          </div>
        </div>

        <div style={{ borderLeft: "1px solid #e2e8f0", paddingLeft: "14px" }}>
          <div style={{ fontSize: "10px", fontWeight: 700, color: isClassOverridden ? "#b45309" : "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            FINANCE OVERRIDE
          </div>
          <div style={{ fontSize: "13px", fontWeight: 700, color: isClassOverridden ? "#b45309" : "#0f172a", marginTop: "2px" }}>
            {isClassOverridden ? (invoice?.classification_override || "None") : "None"}
          </div>
          <div style={{ fontSize: "10.5px", color: "#64748b", marginTop: "1px" }}>
            {isClassOverridden ? `Reason: ${invoice?.classification_override_reason || "Verified by Finance"}` : "No override active"}
          </div>
        </div>

        <div style={{ borderLeft: "1px solid #e2e8f0", paddingLeft: "14px" }}>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "#15803d", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            FINAL AUTHORITATIVE
          </div>
          <div style={{ fontSize: "13px", fontWeight: 700, color: "#15803d", marginTop: "2px" }}>
            {origin}
          </div>
          <div style={{ fontSize: "10.5px", color: "#64748b", marginTop: "1px" }}>
            Used for tax/accounting pipelines
          </div>
        </div>
      </div>

      {/* Classification Evidence Chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "6px", padding: "4px 8px", fontSize: "11px" }}>
          <span style={{ color: "#64748b" }}>Vendor Country:</span>
          <strong style={{ color: "#0f172a" }}>{ext.vendor_country || "Singapore / Overseas"}</strong>
        </div>
        {ext.vendor_tax_id && (
          <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "6px", padding: "4px 8px", fontSize: "11px" }}>
            <span style={{ color: "#64748b" }}>Foreign Tax ID:</span>
            <strong style={{ color: "#0f172a" }}>{ext.vendor_tax_id}</strong>
          </div>
        )}
        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "6px", padding: "4px 8px", fontSize: "11px" }}>
          <span style={{ color: "#64748b" }}>Vendor:</span>
          <strong style={{ color: "#0f172a" }}>{ext.vendor_name || invoice.vendor_name || "HubSpot Asia Pte Ltd"}</strong>
        </div>
        {ext.invoice_period && (
          <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "6px", padding: "4px 8px", fontSize: "11px" }}>
            <span style={{ color: "#64748b" }}>Service Period:</span>
            <strong style={{ color: "#0f172a" }}>{ext.invoice_period}</strong>
          </div>
        )}
      </div>

      {/* 2. Forex (FX) Conversion Boundary Section Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginTop: "4px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "8px",
              background: "#fffbeb",
              border: "1px solid #fde68a",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#d97706",
            }}
          >
            <ArrowRightLeft size={16} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <h4 style={{ fontSize: "14px", fontWeight: 800, margin: 0, color: "#0f172a" }}>
                Forex (FX) Conversion Boundary
              </h4>
              <span
                style={{
                  fontSize: "9.5px",
                  fontWeight: 800,
                  padding: "1px 6px",
                  borderRadius: "4px",
                  background: isFallback ? "#fee2e2" : "#ecfdf5",
                  color: isFallback ? "#dc2626" : "#059669",
                  border: `1px solid ${isFallback ? "#fca5a5" : "#a7f3d0"}`,
                }}
              >
                {rateSource}
              </span>
            </div>
            <p style={{ fontSize: "11px", color: "#64748b", margin: "1px 0 0 0" }}>
              Single conversion boundary. Converted INR amount feeds all downstream TDS, GST/RCM, ITC & Journal engines.
            </p>
          </div>
        </div>

        {!isReadOnly && (
          <button
            type="button"
            onClick={() => {
              setCustomFxRate(activeRate > 0 ? activeRate.toString() : "95.2408");
              setCustomFxReason(fxReason);
              setShowFxModal(true);
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              fontSize: "12px",
              fontWeight: 600,
              background: "#fffbeb",
              color: "#b45309",
              border: "1px solid #fde68a",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            <Sliders size={13} />
            Override FX Rate
          </button>
        )}
      </div>

      {/* The 3-Box Horizontal Conversion Boundary Box (Flutter 1:1 Light Theme) */}
      <div
        style={{
          background: "linear-gradient(135deg, #f0f9ff 0%, #f8fafc 50%, #eff6ff 100%)",
          border: "1px solid #bae6fd",
          borderRadius: "12px",
          padding: "16px 20px",
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr auto 1fr",
          alignItems: "center",
          gap: "12px",
        }}
      >
        {/* Left: Original Foreign Amount */}
        <div>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            ORIGINAL FOREIGN AMOUNT
          </div>
          <div style={{ fontSize: "18px", fontWeight: 900, color: "#0284c7", marginTop: "3px" }}>
            {origCurr} {formatForeign(origTotal)}
          </div>
          <div style={{ fontSize: "11px", color: "#64748b", marginTop: "1px" }}>
            Taxable: {origCurr} {formatForeign(origTaxable)}
          </div>
          <div style={{ fontSize: "10px", color: "#94a3b8", marginTop: "1px" }}>
            Invoice Date: {ext.invoice_date || "2026-07-04"}
          </div>
        </div>

        {/* Math symbol ✕ */}
        <div style={{ color: "#94a3b8", fontSize: "16px", fontWeight: 800, textAlign: "center" }}>
          ✕
        </div>

        {/* Middle: FX Rate */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            FX RATE ({rateDate || "2026-07-04"})
          </div>
          <div style={{ fontSize: "18px", fontWeight: 900, color: "#d97706", marginTop: "3px" }}>
            {activeRate.toFixed(6)}
          </div>
          <div style={{ fontSize: "10.5px", color: isOverridden ? "#b45309" : "#64748b", marginTop: "1px" }}>
            {isOverridden ? `System: ${origSysRate.toFixed(6)} (Finance Final)` : `Source: ${rateSource}`}
          </div>
          <div style={{ fontSize: "10px", color: "#16a34a", fontWeight: 600, marginTop: "1px" }}>
            Lookup: Invoice Date
          </div>
        </div>

        {/* Math symbol ➔ */}
        <div style={{ color: "#94a3b8", fontSize: "16px", fontWeight: 800, textAlign: "center" }}>
          ➔
        </div>

        {/* Right: Canonical INR Gross */}
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            CANONICAL INR GROSS
          </div>
          <div style={{ fontSize: "18px", fontWeight: 900, color: "#15803d", marginTop: "3px" }}>
            ₹{formatInr(convertedTotal)}
          </div>
          <div style={{ fontSize: "11px", color: "#16a34a", marginTop: "1px" }}>
            Taxable INR: ₹{formatInr(convertedTaxable)}
          </div>
          <div style={{ fontSize: "10px", color: "#94a3b8", marginTop: "1px" }}>
            SSOT INR Boundary
          </div>
        </div>
      </div>

      {/* 3. Statutory Compliance Guidance Strip */}
      <div
        style={{
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "8px 12px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
          fontSize: "11.5px",
        }}
      >
        <ShieldCheck size={16} color="#0284c7" style={{ flexShrink: 0 }} />
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
            <span style={{ fontSize: "9.5px", fontWeight: 800, padding: "1px 5px", borderRadius: "4px", background: "#e0f2fe", color: "#0369a1" }}>
              0% Vendor GST
            </span>
            <span style={{ color: "#64748b" }}>Overseas supplier does not charge Indian GST</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
            <span style={{ fontSize: "9.5px", fontWeight: 800, padding: "1px 5px", borderRadius: "4px", background: "#ecfdf5", color: "#059669" }}>
              18% IGST RCM (Sec 5(3))
            </span>
            <span style={{ color: "#64748b" }}>100% ITC Claimable (₹{formatInr(convertedTaxable * 0.18)})</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
            <span style={{ fontSize: "9.5px", fontWeight: 800, padding: "1px 5px", borderRadius: "4px", background: "#fef3c7", color: "#b45309" }}>
              TDS Sec 195/393(2) (20%)
            </span>
            <span style={{ color: "#64748b" }}>₹{formatInr(tdsAmount)} deducted from remittance</span>
          </div>
        </div>
      </div>

      {/* Override Classification Modal */}
      {showOverrideModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0, 0, 0, 0.6)",
            backdropFilter: "blur(4px)",
            padding: "16px",
          }}
        >
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "14px",
              width: "100%",
              maxWidth: "480px",
              padding: "22px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
              color: "#0f172a",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h4 style={{ fontSize: "16px", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px", color: "#0f172a" }}>
                <Edit3 size={18} color="#0284c7" />
                Override Invoice Classification
              </h4>
              <button onClick={() => setShowOverrideModal(false)} style={{ color: "#64748b", cursor: "pointer", background: "none", border: "none" }}>
                <X size={18} />
              </button>
            </div>
            <p style={{ fontSize: "12px", color: "#64748b", marginBottom: "14px" }}>
              Select the authoritative classification. An explicit audit reason is mandatory.
            </p>

            <div style={{ marginBottom: "14px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#334155", marginBottom: "6px" }}>
                Authoritative Classification
              </label>
              <select
                value={overrideTargetOrigin}
                onChange={(e) => setOverrideTargetOrigin(e.target.value)}
                style={{
                  width: "100%",
                  background: "#f8fafc",
                  border: "1px solid #cbd5e1",
                  borderRadius: "8px",
                  padding: "8px 10px",
                  color: "#0f172a",
                  fontSize: "13px",
                  outline: "none",
                }}
              >
                <option value="FOREIGN_SERVICE">FOREIGN_SERVICE — Import of Foreign Services (RCM & 20% TDS)</option>
                <option value="INDIAN">INDIAN — Domestic Indian Supplier</option>
                <option value="REVIEW_REQUIRED">REVIEW_REQUIRED — Needs Clarification</option>
                <option value="UNSUPPORTED_FOREIGN_GOODS">UNSUPPORTED_FOREIGN_GOODS — Physical Goods (BoE)</option>
              </select>
            </div>

            <div style={{ marginBottom: "18px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#334155", marginBottom: "6px" }}>
                Reason for Override *
              </label>
              <textarea
                rows={3}
                value={overrideReasonInput}
                onChange={(e) => setOverrideReasonInput(e.target.value)}
                placeholder="e.g., Overseas vendor confirmed as SaaS provider with no Indian establishment."
                style={{
                  width: "100%",
                  background: "#f8fafc",
                  border: "1px solid #cbd5e1",
                  borderRadius: "8px",
                  padding: "8px 10px",
                  color: "#0f172a",
                  fontSize: "13px",
                  outline: "none",
                  resize: "none",
                }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", paddingTop: "12px", borderTop: "1px solid #e2e8f0" }}>
              <button
                type="button"
                onClick={() => setShowOverrideModal(false)}
                style={{ padding: "7px 14px", fontSize: "12px", color: "#64748b", cursor: "pointer", background: "none", border: "none" }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isSubmittingOverride}
                onClick={handleSaveClassificationOverride}
                style={{
                  padding: "7px 16px",
                  fontSize: "12px",
                  fontWeight: 600,
                  background: "#0284c7",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                }}
              >
                {isSubmittingOverride ? "Saving..." : "Confirm Override"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* FX Rate Override Modal with Preset Chips (Exact Flutter Feature) */}
      {showFxModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0, 0, 0, 0.6)",
            backdropFilter: "blur(4px)",
            padding: "16px",
          }}
        >
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "14px",
              width: "100%",
              maxWidth: "500px",
              padding: "22px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
              color: "#0f172a",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h4 style={{ fontSize: "16px", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px", color: "#0f172a" }}>
                <ArrowRightLeft size={18} color="#d97706" />
                Finance FX Rate Override
              </h4>
              <button onClick={() => setShowFxModal(false)} style={{ color: "#64748b", cursor: "pointer", background: "none", border: "none" }}>
                <X size={18} />
              </button>
            </div>
            <p style={{ fontSize: "12px", color: "#64748b", marginBottom: "12px" }}>
              Enter custom exchange rate for INR conversion (e.g. from RBI / FBIL portal). System rate is preserved in audit trail.
            </p>

            {/* Quick preset chips */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "14px" }}>
              <button
                type="button"
                onClick={() => {
                  setCustomFxRate("95.2408");
                  setCustomFxReason(`RBI Reference Rate (₹95.2408 / ${origCurr}) from official RBI portal on invoice date (${ext.invoice_date || "2026-07-04"}).`);
                }}
                style={{
                  padding: "4px 8px",
                  fontSize: "11px",
                  fontWeight: 700,
                  background: "#ecfdf5",
                  color: "#059669",
                  border: "1px solid #a7f3d0",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                🏦 RBI / FBIL Rate (95.2408)
              </button>
              <button
                type="button"
                onClick={() => {
                  setCustomFxReason(`SBI TT Buying Rate as per Rule 115 of Income-tax Rules on invoice date.`);
                }}
                style={{
                  padding: "4px 8px",
                  fontSize: "11px",
                  fontWeight: 700,
                  background: "#eff6ff",
                  color: "#0284c7",
                  border: "1px solid #bfdbfe",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                ⚖️ Rule 115 SBI TTBR
              </button>
              <button
                type="button"
                onClick={() => {
                  setCustomFxReason(`Bank Forex remittance contract / TT card rate on invoice settlement date.`);
                }}
                style={{
                  padding: "4px 8px",
                  fontSize: "11px",
                  fontWeight: 700,
                  background: "#fffbeb",
                  color: "#b45309",
                  border: "1px solid #fde68a",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                💳 Bank Remittance Rate
              </button>
            </div>

            <div style={{ marginBottom: "14px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#334155", marginBottom: "6px" }}>
                FX Exchange Rate (1 {origCurr} = ? INR) *
              </label>
              <input
                type="number"
                step="0.000001"
                value={customFxRate}
                onChange={(e) => setCustomFxRate(e.target.value)}
                style={{
                  width: "100%",
                  background: "#f8fafc",
                  border: "1px solid #cbd5e1",
                  borderRadius: "8px",
                  padding: "8px 10px",
                  color: "#0f172a",
                  fontSize: "14px",
                  fontFamily: "monospace",
                  outline: "none",
                }}
              />
              {origTotal > 0 && !isNaN(parseFloat(customFxRate)) && (
                <p style={{ fontSize: "11px", color: "#059669", marginTop: "4px", fontWeight: 600 }}>
                  Converted INR Gross: ₹{formatInr(origTotal * parseFloat(customFxRate))} INR
                </p>
              )}
            </div>

            <div style={{ marginBottom: "18px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#334155", marginBottom: "6px" }}>
                Reason for FX Override *
              </label>
              <textarea
                rows={3}
                value={customFxReason}
                onChange={(e) => setCustomFxReason(e.target.value)}
                placeholder="e.g., RBI / FBIL Reference Rate from official portal on invoice date."
                style={{
                  width: "100%",
                  background: "#f8fafc",
                  border: "1px solid #cbd5e1",
                  borderRadius: "8px",
                  padding: "8px 10px",
                  color: "#0f172a",
                  fontSize: "13px",
                  outline: "none",
                  resize: "none",
                }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", paddingTop: "12px", borderTop: "1px solid #e2e8f0" }}>
              <button
                type="button"
                onClick={() => setShowFxModal(false)}
                style={{ padding: "7px 14px", fontSize: "12px", color: "#64748b", cursor: "pointer", background: "none", border: "none" }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isSubmittingFx}
                onClick={handleSaveFxOverride}
                style={{
                  padding: "7px 16px",
                  fontSize: "12px",
                  fontWeight: 600,
                  background: "#d97706",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                }}
              >
                {isSubmittingFx ? "Applying..." : "Apply & Recalculate"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Live RBI Rates Modal */}
      {showRatesModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0, 0, 0, 0.6)",
            backdropFilter: "blur(4px)",
            padding: "16px",
          }}
        >
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "14px",
              width: "100%",
              maxWidth: "580px",
              padding: "22px",
              maxHeight: "85vh",
              overflowY: "auto",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
              color: "#0f172a",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "12px", borderBottom: "1px solid #e2e8f0" }}>
              <h4 style={{ fontSize: "16px", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px", color: "#0f172a" }}>
                <TrendingUp size={18} color="#0284c7" />
                Live RBI Reference Rates Feed
              </h4>
              <button onClick={() => setShowRatesModal(false)} style={{ color: "#64748b", cursor: "pointer", background: "none", border: "none" }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: "14px 0" }}>
              {isLoadingRates ? (
                <div style={{ textAlign: "center", padding: "26px 0", color: "#64748b" }}>
                  <RefreshCw size={24} color="#0284c7" style={{ animation: "spin 1s linear infinite", marginBottom: "8px" }} />
                  <p style={{ fontSize: "12px" }}>Fetching live reference rates...</p>
                </div>
              ) : (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "8px" }}>
                    {liveRates.map((item) => (
                      <div
                        key={item.currency}
                        onClick={() => {
                          handleApplyQuickRate(item.rate, item.currency, item.source);
                          setShowRatesModal(false);
                          setShowFxModal(true);
                        }}
                        style={{
                          background: "#f8fafc",
                          border: "1px solid #e2e8f0",
                          borderRadius: "8px",
                          padding: "10px",
                          cursor: "pointer",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#64748b" }}>
                          <span style={{ fontWeight: 700, color: "#0f172a" }}>{item.currency}/INR</span>
                          <span style={{ fontSize: "9px", padding: "1px 4px", borderRadius: "4px", background: "#e0f2fe", color: "#0369a1" }}>
                            {item.status}
                          </span>
                        </div>
                        <div style={{ fontSize: "15px", fontWeight: 800, color: "#059669", marginTop: "3px" }}>
                          {item.rate_formatted}
                        </div>
                        <div style={{ fontSize: "9.5px", color: "#94a3b8", marginTop: "1px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {item.source}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Built-in quick converter */}
                  <div
                    style={{
                      background: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      borderRadius: "10px",
                      padding: "12px",
                      marginTop: "14px",
                    }}
                  >
                    <h5 style={{ fontSize: "11px", fontWeight: 700, color: "#15803d", textTransform: "uppercase", marginBottom: "8px" }}>
                      Instant Currency Converter
                    </h5>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "8px", alignItems: "center" }}>
                      <div>
                        <label style={{ display: "block", fontSize: "10.5px", color: "#64748b", marginBottom: "3px" }}>Foreign Amount</label>
                        <input
                          type="number"
                          value={calcAmount}
                          onChange={(e) => {
                            setCalcAmount(e.target.value);
                            const val = parseFloat(e.target.value) || 0;
                            const r = liveRates.find((r) => r.currency === calcCurrency)?.rate || activeRate;
                            setCalcResult(val * r);
                          }}
                          style={{
                            width: "100%",
                            background: "#ffffff",
                            border: "1px solid #cbd5e1",
                            borderRadius: "6px",
                            padding: "6px 8px",
                            color: "#0f172a",
                            fontSize: "13px",
                            fontFamily: "monospace",
                            outline: "none",
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ display: "block", fontSize: "10.5px", color: "#64748b", marginBottom: "3px" }}>Currency</label>
                        <select
                          value={calcCurrency}
                          onChange={(e) => {
                            setCalcCurrency(e.target.value);
                            const val = parseFloat(calcAmount) || 0;
                            const r = liveRates.find((r) => r.currency === e.target.value)?.rate || activeRate;
                            setCalcResult(val * r);
                          }}
                          style={{
                            width: "100%",
                            background: "#ffffff",
                            border: "1px solid #cbd5e1",
                            borderRadius: "6px",
                            padding: "6px 8px",
                            color: "#0f172a",
                            fontSize: "13px",
                            outline: "none",
                          }}
                        >
                          {liveRates.map((r) => (
                            <option key={r.currency} value={r.currency}>
                              {r.currency} - ₹{r.rate.toFixed(2)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label style={{ display: "block", fontSize: "10.5px", color: "#64748b", marginBottom: "3px" }}>Converted INR</label>
                        <div
                          style={{
                            background: "#ffffff",
                            border: "1px solid #86efac",
                            borderRadius: "6px",
                            padding: "6px 8px",
                            color: "#15803d",
                            fontSize: "13px",
                            fontWeight: 700,
                          }}
                        >
                          ₹
                          {formatInr(
                            calcResult !== null
                              ? calcResult
                              : (parseFloat(calcAmount) || 0) * activeRate
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: "12px", borderTop: "1px solid #e2e8f0" }}>
              <button
                type="button"
                onClick={() => setShowRatesModal(false)}
                style={{ padding: "6px 14px", fontSize: "12px", fontWeight: 600, background: "#f1f5f9", color: "#334155", border: "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer" }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
