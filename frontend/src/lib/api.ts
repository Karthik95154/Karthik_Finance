export interface LineItem {
  line_index?: number | null;
  description?: string | null;
  hsn_code?: string | null;
  quantity?: number | null;
  unit?: string | null;
  unit_price?: number | null;
  rate?: number | null;
  discount?: number | null;
  discount_type?: string | null;
  line_amount?: number | null;
  taxable_amount?: number | null;
  gst_rate?: number | null;
  cgst_rate?: number | null;
  cgst_amount?: number | null;
  sgst_rate?: number | null;
  sgst_amount?: number | null;
  igst_rate?: number | null;
  igst_amount?: number | null;
  cess_rate?: number | null;
  cess_amount?: number | null;
  account_name?: string | null;
  total?: number | null;
  original_currency?: string | null;
  original_unit_price?: number | null;
  original_taxable_amount?: number | null;
  original_total_amount?: number | null;
}

export interface BankDetails {
  account_holder_name?: string | null;
  account_number?: string | null;
  ifsc_code?: string | null;
  bank_name?: string | null;
  branch?: string | null;
  upi_id?: string | null;
  raw_text?: string | null;
}

export interface ExtractedInvoiceData {
  schema_version?: string | null;
  knowledge_version?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  po_number?: string | null;
  place_of_supply?: string | null;

  vendor_name?: string | null;
  vendor_address?: string | null;
  vendor_gstin?: string | null;
  vendor_pan?: string | null;
  vendor_cin?: string | null;
  vendor_phone?: string | null;
  vendor_email?: string | null;

  customer_name?: string | null;
  customer_address?: string | null;
  customer_gstin?: string | null;
  customer_pan?: string | null;
  customer_phone?: string | null;
  customer_email?: string | null;

  shipping_name?: string | null;
  shipping_address?: string | null;
  shipping_gstin?: string | null;

  payment_terms?: string | null;
  bank_details?: BankDetails | null;

  line_items?: LineItem[];

  subtotal?: number | null;
  discount_total?: number | null;
  taxable_amount?: number | null;
  tax_total?: number | null;
  cgst?: number | null;
  cgst_amount?: number | null;
  sgst?: number | null;
  sgst_amount?: number | null;
  igst?: number | null;
  igst_amount?: number | null;
  cess?: number | null;
  cess_amount?: number | null;
  shipping_charges?: number | null;
  other_charges?: number | null;
  adjustment?: number | null;
  round_off?: number | null;
  total_amount?: number | null;
  currency?: string | null;
  vendor_country?: string | null;
  vendor_tax_id?: string | null;
  original_currency?: string | null;
  original_total_amount?: number | null;
  original_taxable_amount?: number | null;
  exchange_rate?: number | null;
  exchange_rate_date?: string | null;
  exchange_rate_source?: string | null;
  fx_rate_overridden?: boolean | null;
  fx_override_reason?: string | null;
  fx_original_rate?: number | null;
  converted_total_inr?: number | null;
  converted_taxable_inr?: number | null;
  notes?: string | null;
  terms_and_conditions?: string | null;
  invoice_period?: string | null;

  additional_fields?: Record<string, any>;
}

export interface RawVlmOutput {
  data?: ExtractedInvoiceData;
  field_sources?: Record<string, string>;
  line_item_reconciliation?: any[];
  invoice_reconciliation?: Record<string, any>;
  needs_review?: boolean;
  review_reasons?: string[];
  generation_path?: string;
}

export interface AccountingLineItem {
  line_index: number;
  source_description: string;
  account_id?: string | null;
  account_name?: string | null;
  confidence_score?: number | null;
  accounting_reason?: string | null;
  ai_account_id?: string | null;
  ai_account_name?: string | null;
  ai_confidence?: number | null;
  ai_needs_review?: boolean | null;
  final_account_id?: string | null;
  final_account_name?: string | null;
  approved_account_id?: string | null;
  approved_account_name?: string | null;
  tax_analysis?: {
    tax_present?: boolean;
    tax_types?: string[];
    cgst_rate?: number | null;
    cgst_amount?: number | null;
    sgst_rate?: number | null;
    sgst_amount?: number | null;
    igst_rate?: number | null;
    igst_amount?: number | null;
    calculated_tax_amount?: number | null;
    tax_confidence?: number | null;
    tax_needs_review?: boolean | null;
    zoho_tax_name?: string | null;
  } | null;
}

export interface TdsResult {
  applicable?: boolean | null;
  tds_applicable?: boolean | null;
  tds_type?: string | null;
  nature_of_payment?: string | null;
  tds_provision?: string | null;
  provision?: string | null;
  tds_section?: string | null;
  section?: string | null;
  tds_rate?: number | null;
  rate?: number | null;
  approved_tds_rate?: number | null;
  rate_source?: string | null;
  tds_base_amount?: number | null;
  base_amount?: number | null;
  base_source?: string | null;
  extracted_tds_amount?: number | null;
  calculated_tds_amount?: number | null;
  proposed_tds_amount?: number | null;
  tds_amount?: number | null;
  calculation?: string | null;
  confidence?: number | null;
  needs_review?: boolean | null;
  reason?: string | null;
  tds_reasoning?: string | null;
  is_approved?: boolean | null;
  approval_status?: "PENDING" | "APPROVED" | string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  vendor_declared_tds?: {
    present: boolean;
    amount?: number | null;
    rate?: number | null;
    derived_rate?: number | null;
    raw_text?: string | null;
  } | null;
  tds_needs_review?: boolean | null;
  tds_conflict_code?: string | null;
  tds_conflict_reason?: string | null;
  previous_ytd?: number | null;
  projected_ytd?: number | null;
  threshold_amount?: number | null;
  threshold_status?: string | null;
  single_invoice_threshold?: number | null;
  current_invoice_amount?: number | null;
}

export interface AccountingOutput {
  accounting?: AccountingLineItem[];
  tds?: TdsResult | null;
  tds_assessment?: TdsResult | null;
  vendor_declared_tds?: any;
}

export interface InvoiceListItem {
  id: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  status: string;
  accounting_status?: string | null;
  approval_status?: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | string | null;
  export_status?: "NOT_EXPORTED" | "EXPORTED" | "FAILED" | string | null;
  zoho_bill_id?: string | null;
  zoho_bill_number?: string | null;
  vendor_name?: string | null;
  invoice_number?: string | null;
  total_amount?: number | null;
  created_at: string;
  updated_at: string;
}

export interface GstResult {
  supplier_state_code?: string | null;
  supplier_state_name?: string | null;
  buyer_state_code?: string | null;
  buyer_state_name?: string | null;
  place_of_supply_state_code?: string | null;
  place_of_supply_state_name?: string | null;
  place_of_supply_source?: string | null;
  supply_type?: "INTRA_STATE" | "INTER_STATE" | "REVIEW_REQUIRED" | string;
  is_reverse_charge?: boolean;
  extracted?: {
    cgst_amount?: number | null;
    sgst_amount?: number | null;
    igst_amount?: number | null;
    tax_total?: number | null;
  };
  calculated?: {
    cgst_amount?: number | null;
    sgst_amount?: number | null;
    igst_amount?: number | null;
    gst_total?: number | null;
  };
  line_validations?: Array<{
    line_index: number;
    description: string;
    taxable_amount?: number | null;
    extracted_cgst?: number | null;
    extracted_sgst?: number | null;
    extracted_igst?: number | null;
    calculated_cgst?: number | null;
    calculated_sgst?: number | null;
    calculated_igst?: number | null;
  }>;
  validation_status?: "PASSED" | "GST_MISMATCH" | "REVIEW_REQUIRED" | string;
  errors?: string[];
  warnings?: string[];
}

export interface ItcLineItemBreakdown {
  line_index: number;
  description: string;
  account_name?: string | null;
  hsn_code?: string | null;
  tax_amount?: number | null;
  itc_status: "ELIGIBLE" | "PARTIALLY_ELIGIBLE" | "INELIGIBLE" | "REVIEW_REQUIRED" | string;
  eligible_amount: number;
  ineligible_amount: number;
  blocked_amount?: number;
  reversal_amount?: number;
  review_amount?: number;
  net_itc_available?: number;
  reason: string;
  rule_reference: string;
  evidence_used?: string[];
  exceptions_evaluated?: string[];
}

export interface ItcResult {
  status: "ELIGIBLE" | "PARTIALLY_ELIGIBLE" | "INELIGIBLE" | "REVIEW_REQUIRED" | string;
  eligible_amount: number;
  ineligible_amount: number;
  eligible_itc?: number;
  blocked_itc?: number;
  reversal_itc?: number;
  review_amount?: number;
  net_itc_available?: number;
  total_tax_amount: number;
  is_reverse_charge?: boolean;
  supply_type?: string;
  document_type?: string;
  gstr2b_status?: string;
  payment_reversal_status?: string;
  reason: string;
  rule_reference: string;
  warnings?: string[];
  errors?: string[];
  evidence?: string[];
  line_item_breakdown?: ItcLineItemBreakdown[];
}

export interface FinancialCheck {
  name: string;
  description: string;
  status: "PASSED" | "MISMATCH" | "REVIEW_REQUIRED" | "NOT_APPLICABLE" | "MATCH" | "NOT_VALIDATED" | string;
  type?: "LINE_TOTAL" | "SUBTOTAL" | "TAX" | "GRAND_TOTAL" | string;
  field?: string;
  line_item_index?: number;
  line_item_name?: string;
  source_value?: number | null;
  calculated_value?: number | null;
  difference?: number | null;
  note?: string;
  message?: string;
  total_lines_checked?: number;
  line_breakdowns?: Array<{
    line_index: number;
    description: string;
    quantity?: number | null;
    unit_price?: number | null;
    discount?: number | null;
    extracted_taxable?: number | null;
    calculated_taxable?: number | null;
    difference?: number | null;
    status: string;
    note?: string;
  }>;
}

export interface FinancialValidationResult {
  overall_status: "PASSED" | "MISMATCH" | "REVIEW_REQUIRED" | string;
  validation_status?: "VALID" | "MISMATCH" | "PARTIAL" | "NOT_VALIDATED" | string;
  tolerance?: number;
  source: {
    subtotal?: number | null;
    cgst_amount?: number | null;
    sgst_amount?: number | null;
    igst_amount?: number | null;
    cess_amount?: number | null;
    tax_total?: number | null;
    discount_total?: number | null;
    shipping_charges?: number | null;
    other_charges?: number | null;
    round_off?: number | null;
    total_amount?: number | null;
  };
  calculated: {
    subtotal?: number | null;
    gst_total?: number | null;
    grand_total?: number | null;
  };
  differences?: {
    subtotal?: number | null;
    tax_total?: number | null;
    total_amount?: number | null;
  };
  checks: FinancialCheck[];
  errors: string[];
  warnings: string[];
}

export interface JournalLine {
  account_id: string;
  account_name: string;
  line_type: "EXPENSE" | "ASSET" | "INPUT_TAX" | "TDS_PAYABLE" | "ACCOUNTS_PAYABLE" | "ROUND_OFF" | string;
  debit: number;
  credit: number;
  source_line_index?: number | null;
  provenance: "AI_PREDICTED" | "HITL_OVERRIDE" | "DETERMINISTIC" | string;
  description?: string | null;
  match_status?: string | null;
  ai_needs_review?: boolean | null;
  match_message?: string | null;
}

export interface JournalValidation {
  balanced: boolean;
  tolerance: number;
  errors: string[];
  warnings: string[];
}

export interface JournalEntry {
  status: "BALANCED" | "APPROVED" | "REVIEW_REQUIRED" | "UNBALANCED" | string;
  approval_status?: "PENDING" | "APPROVED" | string;
  approved_by?: string | null;
  approved_at?: string | null;
  total_debit: number;
  total_credit: number;
  difference: number;
  currency: string;
  lines: JournalLine[];
  validation: JournalValidation;
  is_balanced?: boolean;
}

export interface Invoice {
  id: string;
  file_path: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  file_hash: string;
  status: "PENDING" | "PROCESSING_VLM" | "PROCESSING_ACCOUNTING" | "COMPLETED" | "FAILED" | string;
  accounting_status?: "PENDING" | "PROCESSING_ACCOUNTING" | "COMPLETED" | "FAILED" | string | null;
  approval_status?: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | string | null;
  export_status?: "NOT_EXPORTED" | "EXPORTED" | "FAILED" | string | null;
  period_category?: "PREVIOUS_FINANCIAL_YEAR" | "CURRENT_FINANCIAL_YEAR" | string | null;
  period_decision?: "NOT_REQUIRED" | "PENDING" | "CONTINUE" | "CANCELLED" | string | null;
  invoice_date?: string | null;
  zoho_bill_id?: string | null;
  zoho_bill_number?: string | null;
  error_message?: string | null;
  confidence_score?: number | null;
  accounting_confidence?: number | null;
  invoice_origin?: "INDIAN" | "FOREIGN_SERVICE" | "REVIEW_REQUIRED" | "UNSUPPORTED_FOREIGN_GOODS" | string | null;
  classification_override?: string | null;
  classification_override_reason?: string | null;
  classified_by?: string | null;
  classified_at?: string | null;
  classification_source?: string | null;
  original_currency?: string | null;
  original_total_amount?: number | null;
  original_taxable_amount?: number | null;
  exchange_rate?: number | null;
  exchange_rate_date?: string | null;
  exchange_rate_source?: string | null;
  fx_rate_overridden?: boolean | null;
  fx_override_reason?: string | null;
  fx_original_rate?: number | null;
  converted_total_inr?: number | null;
  converted_taxable_inr?: number | null;
  raw_vlm_output?: RawVlmOutput | null;
  current_vlm_output?: RawVlmOutput | null;
  accounting_output?: AccountingOutput | null;
  current_accounting_output?: AccountingOutput | null;
  gst_result?: GstResult | null;
  itc_result?: ItcResult | null;
  financial_validation_result?: FinancialValidationResult | null;
  journal_entry?: JournalEntry | null;
  vendor_name?: string | null;
  currency?: string | null;
  is_foreign?: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface InvoiceStatus {
  invoice_id: string;
  status: "PENDING" | "PROCESSING_VLM" | "PROCESSING_ACCOUNTING" | "COMPLETED" | "FAILED" | "CANCELLED" | string;
  accounting_status?: string | null;
  approval_status?: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | string | null;
  export_status?: "NOT_EXPORTED" | "EXPORTED" | "FAILED" | string | null;
  error_message?: string | null;
  confidence_score?: number | null;
  accounting_confidence?: number | null;
  period_category?: "CURRENT_MONTH" | "PREVIOUS_MONTH_CURRENT_FY" | "PREVIOUS_FINANCIAL_YEAR" | "CURRENT_FINANCIAL_YEAR" | "FUTURE_PERIOD" | string | null;
  period_decision?: "NOT_REQUIRED" | "PENDING" | "CONTINUE" | "CANCELLED" | string | null;
  period_message?: string | null;
  file_name?: string | null;
  invoice_date?: string | null;
  updated_at: string;
}

export interface UploadResponse {
  invoice_id: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  file_hash: string;
  status: string;
  created_at: string;
}

export interface ServiceHealthDetail {
  name: string;
  status: "online" | "404_error" | "offline" | "connected" | "disconnected" | "degraded" | "error" | "timeout" | string;
  status_code?: number | null;
  message: string;
  latency_ms?: number | null;
  endpoint?: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "error" | string;
  project: string;
  database: string;
  storage: string;
  colab_vlm?: string;
  colab_accounting?: string;
  services?: Record<string, ServiceHealthDetail>;
  timestamp: string;
}

let rawApiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

if (typeof window !== "undefined") {
  const hostname = window.location.hostname;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    rawApiBase = "http://127.0.0.1:8000/api/v1";
  } else if (hostname.includes("devtunnels.ms") || hostname.includes("github.dev")) {
    const backendHost = window.location.host.replace("-3000", "-8000").replace("-3001", "-8000");
    rawApiBase = `${window.location.protocol}//${backendHost}/api/v1`;
  }
}

export const API_BASE = rawApiBase.endsWith("/api/v1")
  ? rawApiBase.replace(/\/+$/, "")
  : `${rawApiBase.replace(/\/+$/, "")}/api/v1`;

export async function uploadInvoice(file: File): Promise<UploadResponse> {
  const authHeaders = await getAuthHeaders();
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/invoices/upload`, {
    method: "POST",
    headers: authHeaders,
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
  }

  return res.json();
}

export async function processInvoice(id: string): Promise<InvoiceStatus> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}/process`, {
    method: "POST",
    headers: authHeaders,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to trigger process for invoice ${id}`);
  }

  return res.json();
}

export async function getInvoiceStatus(id: string): Promise<InvoiceStatus> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}/status`, {
    headers: authHeaders,
    cache: "no-store",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch status for invoice ${id}`);
  }

  return res.json();
}

export async function submitPeriodDecision(
  id: string,
  decision: "CONTINUE" | "CANCEL"
): Promise<{ invoice_id: string; period_decision: string; status: string; message: string }> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}/period-decision`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ decision }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to submit period decision for invoice ${id}`);
  }

  return res.json();
}


export async function listInvoices(forceRefresh = false): Promise<InvoiceListItem[]> {
  const now = Date.now();
  if (!forceRefresh && inMemoryInvoices && now - inMemoryInvoicesTime < 15000) {
    return inMemoryInvoices;
  }

  if (!forceRefresh && !inMemoryInvoices && typeof window !== "undefined") {
    const cached = getCachedInvoices();
    if (cached) {
      fetchFreshInvoices().catch(() => { });
      return cached;
    }
  }

  return await fetchFreshInvoices();
}

const inFlightPromises = new Map<string, Promise<any>>();

function fetchWithInFlightDeduplication<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  if (inFlightPromises.has(key)) {
    return inFlightPromises.get(key) as Promise<T>;
  }

  const promise = fetcher().finally(() => {
    inFlightPromises.delete(key);
  });

  inFlightPromises.set(key, promise);
  return promise;
}

async function fetchFreshInvoices(): Promise<InvoiceListItem[]> {
  return fetchWithInFlightDeduplication("invoices", async () => {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/invoices`, {
      headers: authHeaders,
      cache: "no-store",
    });

    if (!res.ok) {
      if (inMemoryInvoices) return inMemoryInvoices;
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || "Failed to fetch invoices list");
    }

    const data: InvoiceListItem[] = await res.json();
    inMemoryInvoices = data;
    inMemoryInvoicesTime = Date.now();
    if (typeof window !== "undefined") {
      try {
        sessionStorage.setItem(INVOICES_CACHE_KEY, JSON.stringify(data));
      } catch (_) { }
    }
    return data;
  });
}

export async function getInvoice(id: string): Promise<Invoice> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}`, {
    headers: authHeaders,
    cache: "no-store",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch invoice ${id}`);
  }

  return res.json();
}

export async function triggerAccountingCategorization(id: string): Promise<InvoiceStatus> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}/categorize`, {
    method: "POST",
    headers: authHeaders,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to trigger accounting for invoice ${id}`);
  }

  return res.json();
}

export interface InvoiceUpdateRequest {
  current_vlm_output?: RawVlmOutput | null;
  current_accounting_output?: AccountingOutput | null;
  journal_entry?: JournalEntry | null;
  classification_override?: string | null;
  classification_override_reason?: string | null;
  exchange_rate?: number | null;
  fx_override_reason?: string | null;
  exchange_rate_date?: string | null;
  exchange_rate_source?: string | null;
}

export async function updateInvoiceExtraction(
  id: string,
  currentVlmOutput?: RawVlmOutput | null,
  currentAccountingOutput?: AccountingOutput | null,
  journalEntry?: JournalEntry | null,
  extraOverrides?: Partial<InvoiceUpdateRequest>
): Promise<Invoice> {
  const authHeaders = await getAuthHeaders();
  const body: Record<string, any> = {};
  if (currentVlmOutput !== undefined) body.current_vlm_output = currentVlmOutput;
  if (currentAccountingOutput !== undefined) body.current_accounting_output = currentAccountingOutput;
  if (journalEntry !== undefined) body.journal_entry = journalEntry;
  if (extraOverrides) {
    Object.assign(body, extraOverrides);
  }

  const res = await fetch(`${API_BASE}/invoices/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to update invoice ${id}`);
  }

  return res.json();
}

export interface ForexRateItem {
  currency: string;
  target_currency: string;
  rate: number;
  rate_formatted: string;
  rate_date: string;
  source: string;
  is_fallback: boolean;
  status: string;
}

export interface ForexRatesListResponse {
  base: string;
  date: string;
  last_updated: string;
  rates: ForexRateItem[];
  rbi_reference_currencies: string[];
}

export interface CurrencyConversionResponse {
  original_amount: number;
  from_currency: string;
  to_currency: string;
  rate: number;
  converted_amount: number;
  rate_date: string;
  source: string;
}

export async function getForexRates(rateDate?: string): Promise<ForexRatesListResponse> {
  const authHeaders = await getAuthHeaders();
  const query = rateDate ? `?rate_date=${encodeURIComponent(rateDate)}` : "";
  const res = await fetch(`${API_BASE}/forex/rates${query}`, {
    headers: authHeaders,
    cache: "no-store",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to fetch forex rates");
  }
  return res.json();
}

export async function convertCurrency(
  amount: number,
  fromCurrency: string,
  toCurrency = "INR",
  date?: string
): Promise<CurrencyConversionResponse> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/forex/convert`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({
      amount,
      from_currency: fromCurrency,
      to_currency: toCurrency,
      date,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to convert currency");
  }
  return res.json();
}

export function getInvoiceFileUrl(id: string): string {
  return `${API_BASE}/invoices/${id}/file`;
}

export async function fetchAuthenticatedFileBlobUrl(id: string): Promise<string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("dev_auth_token") : null;
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(getInvoiceFileUrl(id), { headers });
  if (!res.ok) {
    throw new Error(`Failed to load file preview (${res.status})`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function getInvoiceJournal(id: string): Promise<JournalEntry> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}/journal`, {
    headers: authHeaders,
    cache: "no-store",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch journal for invoice ${id}`);
  }

  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Health check failed");
  }

  return res.json();
}

// ----------------------------------------------------
// Zoho Integration & Auth Interfaces & API Methods
// ----------------------------------------------------
export interface UserProfile {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
  full_name?: string | null;
  is_active?: boolean;
}

export type ZohoConnectionState = "DISCONNECTED" | "CONNECTED" | "ERROR" | "CONNECTING" | "SYNCING" | "ORGANIZATION_REQUIRED";

export interface ZohoStatusResponse {
  connected: boolean;
  status: ZohoConnectionState;
  organization_id?: string | null;
  organization_name?: string | null;
  accounts_server?: string | null;
  api_domain?: string | null;
  error_message?: string | null;
  last_synced_at?: string | null;
  last_sync_at?: string | null;
  accounts_count?: number;
  taxes_count?: number;
  vendors_count?: number;
}

export interface ZohoOrganization {
  organization_id: string;
  name: string;
  is_default_org?: boolean;
  currency_code?: string;
  time_zone?: string;
}

export interface ZohoMasterDataSummary {
  chart_of_accounts_count: number;
  tax_rates_count: number;
  vendors_count: number;
  last_synced_at?: string | null;
  chart_of_accounts?: any[];
  accounts?: any[];
  tax_rates?: any[];
  taxes?: any[];
  vendors?: any[];
}

export interface JournalPreviewResponse {
  entry_date?: string;
  supply_type?: string;
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
  has_unapproved_lines?: boolean;
  difference?: number;
  lines: any[];
}

let devToken: string | null = null;

/** Call this when a new user logs in to wipe the cached in-memory token. */
export function clearAuthToken() {
  devToken = null;
}

export function getCurrentUserIdFromToken(): string | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem("token") || localStorage.getItem("auth_token") || localStorage.getItem("dev_auth_token") || devToken;
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.sub || payload.user_id || null;
  } catch (_) {
    return null;
  }
}

function isJwtExpired(tokenStr: string): boolean {
  try {
    const parts = tokenStr.split(".");
    if (parts.length < 2) return true;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    const nowSec = Math.floor(Date.now() / 1000);
    return Boolean(payload.exp && payload.exp < nowSec + 30);
  } catch (e) {
    return true;
  }
}

export async function getAuthHeaders(): Promise<Record<string, string>> {
  if (typeof window !== "undefined") {
    const stored =
      localStorage.getItem("token") ||
      localStorage.getItem("auth_token") ||
      localStorage.getItem("dev_auth_token");
    if (stored && stored !== "null" && stored !== "undefined") {
      if (isJwtExpired(stored)) {
        localStorage.removeItem("token");
        localStorage.removeItem("auth_token");
        localStorage.removeItem("dev_auth_token");
        devToken = null;
      } else {
        return { Authorization: `Bearer ${stored}` };
      }
    }
  }
  if (!devToken || isJwtExpired(devToken)) {
    try {
      const res = await fetch(`${API_BASE}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "finance@sakshi.ai",
          dev_role: "ADMIN",
          dev_tenant_id: "default-tenant-001",
          dev_name: "Dev Admin",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        devToken = data.access_token;
        if (typeof window !== "undefined" && devToken) {
          localStorage.setItem("token", devToken);
          localStorage.setItem("auth_token", devToken);
          localStorage.setItem("dev_auth_token", devToken);
        }
      }
    } catch (err) {
      console.warn("Failed to retrieve dev token", err);
    }
  }
  return devToken ? { Authorization: `Bearer ${devToken}` } : {};
}

export async function getCurrentUser(): Promise<UserProfile> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders,
    cache: "no-store",
  });
  if (!res.ok) {
    return { id: "dev-user", email: "finance@sakshi.ai", role: "ADMIN", tenant_id: "default-tenant-001" };
  }
  return res.json();
}

export async function signupUser(payload: { email: string; password: string; full_name?: string }): Promise<{ access_token: string; token_type: string; user: UserProfile }> {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Signup failed" }));
    throw new Error(err.detail || "Signup failed");
  }
  const data = await res.json();
  if (typeof window !== "undefined" && data.access_token) {
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("auth_token", data.access_token);
    localStorage.setItem("dev_auth_token", data.access_token);
    devToken = data.access_token;
  }
  return data;
}

export async function loginUser(payload: { email: string; password: string }): Promise<{ access_token: string; token_type: string; user: UserProfile }> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Invalid email or password" }));
    throw new Error(err.detail || "Invalid email or password");
  }
  const data = await res.json();
  if (typeof window !== "undefined" && data.access_token) {
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("auth_token", data.access_token);
    localStorage.setItem("dev_auth_token", data.access_token);
    devToken = data.access_token;
  }
  return data;
}

export async function logoutUser(): Promise<void> {
  const headers = await getAuthHeaders();
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers,
    });
  } catch (e) {
    // Ignore error
  }
  if (typeof window !== "undefined") {
    localStorage.removeItem("token");
    localStorage.removeItem("auth_token");
    localStorage.removeItem("dev_auth_token");
  }
  devToken = null;
}

export async function switchDevRole(role: string): Promise<UserProfile> {
  try {
    const res = await fetch(`${API_BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "finance@sakshi.ai",
        dev_role: role,
        dev_tenant_id: "default-tenant-001",
        dev_name: `Dev ${role}`,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      devToken = data.access_token;
      if (typeof window !== "undefined" && devToken) {
        localStorage.setItem("dev_auth_token", devToken);
      }
      return data.user;
    }
  } catch (err) {
    console.warn("Failed to switch dev role", err);
  }
  return { id: "dev-user", email: "finance@sakshi.ai", role, tenant_id: "default-tenant-001" };
}


// Cache storage keys & in-memory caches for seamless page navigations
const ZOHO_STATUS_CACHE_KEY = "sakshi_zoho_status_cache";
const ZOHO_MASTER_DATA_CACHE_KEY = "sakshi_zoho_md_cache";
const IMAP_SETTINGS_CACHE_KEY = "sakshi_imap_settings_cache";
let inMemoryZohoStatus: ZohoStatusResponse | null = null;
let inMemoryZohoStatusUserId: string | null = null;
let inMemoryZohoStatusTime = 0;
let inMemoryMasterData: ZohoMasterDataSummary | null = null;
let inMemoryMasterDataUserId: string | null = null;
let inMemoryMasterDataTime = 0;
let inMemoryImapSettings: IMAPSettings | null = null;
let inMemoryImapSettingsTime = 0;

export function getCachedIMAPSettings(): IMAPSettings | null {
  if (inMemoryImapSettings) return inMemoryImapSettings;
  if (typeof window !== "undefined") {
    try {
      const raw = sessionStorage.getItem(IMAP_SETTINGS_CACHE_KEY);
      if (raw) {
        inMemoryImapSettings = JSON.parse(raw);
        return inMemoryImapSettings;
      }
    } catch (_) { }
  }
  return null;
}

export function invalidateIMAPCache() {
  inMemoryImapSettings = null;
  inMemoryImapSettingsTime = 0;
  if (typeof window !== "undefined") {
    try {
      sessionStorage.removeItem(IMAP_SETTINGS_CACHE_KEY);
    } catch (_) { }
  }
}

const INVOICES_CACHE_KEY = "sakshi_invoices_cache";
const STAGED_DOCS_CACHE_KEY = "sakshi_staged_docs_cache";

let inMemoryInvoices: InvoiceListItem[] | null = null;
let inMemoryInvoicesTime = 0;
let inMemoryStagedDocs: StagedDocument[] | null = null;
let inMemoryStagedDocsTime = 0;

export function getCachedInvoices(): InvoiceListItem[] | null {
  if (inMemoryInvoices) return inMemoryInvoices;
  if (typeof window !== "undefined") {
    try {
      const raw = sessionStorage.getItem(INVOICES_CACHE_KEY);
      if (raw) {
        inMemoryInvoices = JSON.parse(raw);
        return inMemoryInvoices;
      }
    } catch (_) { }
  }
  return null;
}

export function invalidateInvoicesCache() {
  inMemoryInvoices = null;
  inMemoryInvoicesTime = 0;
  if (typeof window !== "undefined") {
    try {
      sessionStorage.removeItem(INVOICES_CACHE_KEY);
    } catch (_) { }
  }
}

export function getCachedStagedDocuments(): StagedDocument[] | null {
  if (inMemoryStagedDocs) return inMemoryStagedDocs;
  if (typeof window !== "undefined") {
    try {
      const raw = sessionStorage.getItem(STAGED_DOCS_CACHE_KEY);
      if (raw) {
        inMemoryStagedDocs = JSON.parse(raw);
        return inMemoryStagedDocs;
      }
    } catch (_) { }
  }
  return null;
}

export function invalidateStagedDocumentsCache() {
  inMemoryStagedDocs = null;
  inMemoryStagedDocsTime = 0;
  if (typeof window !== "undefined") {
    try {
      sessionStorage.removeItem(STAGED_DOCS_CACHE_KEY);
    } catch (_) { }
  }
}

export function getCachedZohoStatus(): ZohoStatusResponse | null {
  const currentUserId = getCurrentUserIdFromToken();
  if (inMemoryZohoStatus && inMemoryZohoStatusUserId === currentUserId) return inMemoryZohoStatus;
  if (typeof window !== "undefined" && currentUserId) {
    try {
      const raw = sessionStorage.getItem(`${ZOHO_STATUS_CACHE_KEY}_${currentUserId}`);
      if (raw) {
        inMemoryZohoStatus = JSON.parse(raw);
        inMemoryZohoStatusUserId = currentUserId;
        return inMemoryZohoStatus;
      }
    } catch (_) { }
  }
  return null;
}

export function getCachedMasterData(): ZohoMasterDataSummary | null {
  const currentUserId = getCurrentUserIdFromToken();
  if (inMemoryMasterData && inMemoryMasterDataUserId === currentUserId) return inMemoryMasterData;
  if (typeof window !== "undefined" && currentUserId) {
    try {
      const raw = sessionStorage.getItem(`${ZOHO_MASTER_DATA_CACHE_KEY}_${currentUserId}`);
      if (raw) {
        inMemoryMasterData = JSON.parse(raw);
        inMemoryMasterDataUserId = currentUserId;
        return inMemoryMasterData;
      }
    } catch (_) { }
  }
  return null;
}

export function invalidateZohoCache() {
  const currentUserId = getCurrentUserIdFromToken();
  inMemoryZohoStatus = null;
  inMemoryZohoStatusUserId = null;
  inMemoryZohoStatusTime = 0;
  inMemoryMasterData = null;
  inMemoryMasterDataUserId = null;
  inMemoryMasterDataTime = 0;
  if (typeof window !== "undefined") {
    try {
      if (currentUserId) {
        sessionStorage.removeItem(`${ZOHO_STATUS_CACHE_KEY}_${currentUserId}`);
        sessionStorage.removeItem(`${ZOHO_MASTER_DATA_CACHE_KEY}_${currentUserId}`);
      }
      sessionStorage.removeItem(ZOHO_STATUS_CACHE_KEY);
      sessionStorage.removeItem(ZOHO_MASTER_DATA_CACHE_KEY);
    } catch (_) { }
  }
}

export async function getZohoStatus(forceRefresh = false): Promise<ZohoStatusResponse> {
  const currentUserId = getCurrentUserIdFromToken();
  const now = Date.now();
  if (!forceRefresh && inMemoryZohoStatus && inMemoryZohoStatusUserId === currentUserId && now - inMemoryZohoStatusTime < 20000) {
    return inMemoryZohoStatus;
  }

  if (!forceRefresh && currentUserId) {
    const cached = getCachedZohoStatus();
    if (cached) {
      fetchFreshZohoStatus().catch(() => { });
      return cached;
    }
  }

  return await fetchFreshZohoStatus();
}

async function fetchFreshZohoStatus(): Promise<ZohoStatusResponse> {
  const authHeaders = await getAuthHeaders();
  try {
    const res = await fetch(`${API_BASE}/zoho/status`, {
      headers: authHeaders,
      cache: "no-store",
    });
    if (!res.ok) {
      const fallback: ZohoStatusResponse = { connected: false, status: "DISCONNECTED" };
      return fallback;
    }
    const data: ZohoStatusResponse = await res.json();
    const currentUserId = getCurrentUserIdFromToken();
    inMemoryZohoStatus = data;
    inMemoryZohoStatusUserId = currentUserId;
    inMemoryZohoStatusTime = Date.now();
    if (typeof window !== "undefined") {
      try {
        if (currentUserId) {
          sessionStorage.setItem(`${ZOHO_STATUS_CACHE_KEY}_${currentUserId}`, JSON.stringify(data));
        }
        sessionStorage.setItem(ZOHO_STATUS_CACHE_KEY, JSON.stringify(data));
        window.dispatchEvent(new CustomEvent("zoho-status-updated", { detail: data }));
      } catch (_) { }
    }
    return data;
  } catch (err) {
    if (inMemoryZohoStatus) return inMemoryZohoStatus;
    return { connected: false, status: "DISCONNECTED" };
  }
}

export async function getZohoConnectUrl(accountsServer?: string, redirectUri?: string): Promise<{ auth_url: string; authorization_url?: string; state: string }> {
  let url = `${API_BASE}/zoho/connect`;
  const params = new URLSearchParams();
  if (accountsServer) params.append("accounts_server", accountsServer);
  if (redirectUri) params.append("redirect_uri", redirectUri);
  if (params.toString()) url += `?${params.toString()}`;

  const authHeaders = await getAuthHeaders();
  const res = await fetch(url, {
    headers: authHeaders,
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to get Zoho auth URL");
  }
  return res.json();
}

export async function getZohoOrganizations(): Promise<ZohoOrganization[]> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/zoho/organizations`, {
    headers: authHeaders,
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch Zoho organizations");
  }
  const data = await res.json();
  return Array.isArray(data) ? data : data.organizations || [];
}

export async function selectZohoOrganization(organizationId: string, organizationName?: string): Promise<{ success: boolean; message: string; accounts_synced?: number; taxes_synced?: number; vendors_synced?: number }> {
  const authHeaders = await getAuthHeaders();
  let res = await fetch(`${API_BASE}/zoho/select-org`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ organization_id: organizationId, organization_name: organizationName }),
  });
  if (!res.ok) {
    res = await fetch(`${API_BASE}/zoho/select-organization`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
      },
      body: JSON.stringify({ organization_id: organizationId, organization_name: organizationName }),
    });
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to select Zoho organization");
  }
  const result = await res.json();
  invalidateZohoCache();
  await getZohoStatus(true);
  return result;
}

export async function triggerZohoSync(): Promise<{ message: string; chart_of_accounts?: number; tax_rates?: number; vendors?: number; accounts_synced?: number; taxes_synced?: number; vendors_synced?: number }> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/zoho/sync`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to sync Zoho master data");
  }
  const result = await res.json();
  invalidateZohoCache();
  await Promise.allSettled([getZohoStatus(true), getMasterDataSummary(true)]);
  return result;
}

export async function getMasterDataSummary(forceRefresh = false): Promise<ZohoMasterDataSummary> {
  const now = Date.now();
  if (!forceRefresh && inMemoryMasterData && now - inMemoryMasterDataTime < 30000) {
    return inMemoryMasterData;
  }

  if (!forceRefresh && !inMemoryMasterData && typeof window !== "undefined") {
    const cached = getCachedMasterData();
    if (cached && (cached.chart_of_accounts_count > 0 || cached.tax_rates_count > 0 || cached.vendors_count > 0)) {
      fetchFreshMasterData().catch(() => { });
      return cached;
    }
  }

  return await fetchFreshMasterData();
}

async function fetchFreshMasterData(): Promise<ZohoMasterDataSummary> {
  const authHeaders = await getAuthHeaders();
  try {
    const res = await fetch(`${API_BASE}/zoho/master-data-summary`, {
      headers: authHeaders,
      cache: "no-store",
    });
    if (!res.ok) {
      return { chart_of_accounts_count: 0, tax_rates_count: 0, vendors_count: 0 };
    }
    const data: ZohoMasterDataSummary = await res.json();
    inMemoryMasterData = data;
    inMemoryMasterDataTime = Date.now();
    if (typeof window !== "undefined") {
      try {
        sessionStorage.setItem(ZOHO_MASTER_DATA_CACHE_KEY, JSON.stringify(data));
      } catch (_) { }
    }
    return data;
  } catch (err) {
    if (inMemoryMasterData) return inMemoryMasterData;
    return { chart_of_accounts_count: 0, tax_rates_count: 0, vendors_count: 0 };
  }
}

export async function getZohoMasterData(): Promise<{ accounts: any[]; taxes: any[]; vendors: any[] }> {
  const authHeaders = await getAuthHeaders();
  try {
    const res = await fetch(`${API_BASE}/zoho/master-data`, {
      headers: authHeaders,
      cache: "no-store",
    });
    if (!res.ok) {
      return { accounts: [], taxes: [], vendors: [] };
    }
    const data = await res.json();
    return {
      accounts: data.accounts || [],
      taxes: data.taxes || [],
      vendors: data.vendors || [],
    };
  } catch (err) {
    return { accounts: [], taxes: [], vendors: [] };
  }
}

export async function disconnectZoho(): Promise<{ success: boolean; message: string }> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/zoho/disconnect`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to disconnect Zoho");
  }
  const data = await res.json();
  invalidateZohoCache();
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("zoho-status-updated", {
        detail: { connected: false, status: "DISCONNECTED" },
      })
    );
  }
  return data;
}

export async function approveInvoice(id: string): Promise<Invoice> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/review/invoices/${id}/approve`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve invoice");
  }
  return res.json();
}

export async function approveJournal(id: string): Promise<{
  status: string;
  message: string;
  journal_status: string;
  approval_status: string;
  is_balanced: boolean;
  total_debit: number;
  total_credit: number;
  approved_by: string;
  approved_at: string;
  journal_entry: JournalEntry;
}> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}/journal/approve`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve General Ledger journal");
  }
  return res.json();
}

export async function approveTds(id: string): Promise<{
  status: string;
  message: string;
  tds: TdsResult;
  journal_entry?: JournalEntry;
}> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}/tds/approve`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve TDS assessment");
  }
  return res.json();
}

export async function rejectInvoice(id: string, reason: string): Promise<Invoice> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/review/invoices/${id}/reject`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to reject invoice");
  }
  return res.json();
}

export async function exportInvoiceToZoho(id: string): Promise<{ success: boolean; zoho_bill_id: string; zoho_bill_number: string }> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/zoho/export-bill/${id}`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to export invoice to Zoho");
  }
  return res.json();
}

export async function getJournalPreview(id: string): Promise<JournalPreviewResponse> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${id}/journal`, {
    headers: authHeaders,
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch journal preview");
  }
  return res.json();
}

// ----------------------------------------------------
// IMAP Email & Inbox Staging API Methods
// ----------------------------------------------------
export interface StagedDocument {
  id: string;
  file_name: string;
  file_size?: number | null;
  mime_type?: string | null;
  file_path: string;
  status: string;
  email_sender?: string | null;
  email_subject?: string | null;
  email_received_at?: string | null;
  created_at: string;
  financial_relevance?: string | null;
  document_type?: string | null;
  classification_confidence?: number | null;
  classification_reason?: string | null;
  classification_model?: string | null;
}

export interface IMAPSettings {
  id?: string;
  status?: string;
  is_connected?: boolean;
  config?: {
    imap_server?: string;
    imap_port?: number | string;
    email_address?: string;
    password?: string;
  } | null;
  last_synced_at?: string | null;
  imap_server?: string;
  imap_port?: number | string;
  email_address?: string;
}

export async function listStagedDocuments(forceRefresh = false): Promise<StagedDocument[]> {
  const now = Date.now();
  if (!forceRefresh && inMemoryStagedDocs && now - inMemoryStagedDocsTime < 15000) {
    return inMemoryStagedDocs;
  }

  if (!forceRefresh && !inMemoryStagedDocs && typeof window !== "undefined") {
    const cached = getCachedStagedDocuments();
    if (cached) {
      fetchFreshStagedDocuments().catch(() => { });
      return cached;
    }
  }

  return await fetchFreshStagedDocuments();
}

async function fetchFreshStagedDocuments(): Promise<StagedDocument[]> {
  return fetchWithInFlightDeduplication("staged_docs", async () => {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/inbox/staged`, {
      headers: authHeaders,
      cache: "no-store",
    });
    if (!res.ok) {
      if (inMemoryStagedDocs) return inMemoryStagedDocs;
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to list staged documents");
    }
    const data: StagedDocument[] = await res.json();
    inMemoryStagedDocs = data;
    inMemoryStagedDocsTime = Date.now();
    if (typeof window !== "undefined") {
      try {
        sessionStorage.setItem(STAGED_DOCS_CACHE_KEY, JSON.stringify(data));
      } catch (_) { }
    }
    return data;
  });
}

export async function processStagedDocument(id: string): Promise<any> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/inbox/staged/${id}/process`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to process staged document");
  }
  const result = await res.json();
  invalidateStagedDocumentsCache();
  invalidateInvoicesCache();
  return result;
}

export async function deleteStagedDocument(id: string): Promise<any> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/inbox/staged/${id}`, {
    method: "DELETE",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to delete staged document");
  }
  const result = await res.json();
  invalidateStagedDocumentsCache();
  return result;
}

export async function pollEmails(): Promise<{
  success: boolean;
  emails_checked: number;
  attachments_found: number;
  accepted_attachments: number;
  duplicates: number;
  new_documents: number;
  failed_attachments: number;
  errors: any[];
}> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/inbox/poll`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to poll emails");
  }
  const result = await res.json();
  invalidateStagedDocumentsCache();
  await listStagedDocuments(true);
  return result;
}

export async function getIMAPSettings(forceRefresh = false): Promise<IMAPSettings> {
  const now = Date.now();
  if (!forceRefresh && inMemoryImapSettings && now - inMemoryImapSettingsTime < 20000) {
    return inMemoryImapSettings;
  }

  if (!forceRefresh && !inMemoryImapSettings && typeof window !== "undefined") {
    const cached = getCachedIMAPSettings();
    if (cached) {
      fetchFreshIMAPSettings().catch(() => { });
      return cached;
    }
  }

  return await fetchFreshIMAPSettings();
}

async function fetchFreshIMAPSettings(): Promise<IMAPSettings> {
  const authHeaders = await getAuthHeaders();
  try {
    const res = await fetch(`${API_BASE}/settings/integrations/imap_email`, {
      headers: authHeaders,
      cache: "no-store",
    });
    if (!res.ok) {
      const fallback: IMAPSettings = { imap_server: "imap.gmail.com", imap_port: 993, email_address: "", is_connected: false, status: "disconnected" };
      return fallback;
    }
    const data: IMAPSettings = await res.json();
    inMemoryImapSettings = data;
    inMemoryImapSettingsTime = Date.now();
    if (typeof window !== "undefined") {
      try {
        sessionStorage.setItem(IMAP_SETTINGS_CACHE_KEY, JSON.stringify(data));
      } catch (_) { }
    }
    return data;
  } catch (err) {
    if (inMemoryImapSettings) return inMemoryImapSettings;
    return { imap_server: "imap.gmail.com", imap_port: 993, email_address: "", is_connected: false, status: "disconnected" };
  }
}

export async function configureIMAPSettings(data: {
  imap_server: string;
  imap_port: number;
  email_address: string;
  password?: string;
}): Promise<any> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/settings/integrations/imap_email/configure`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to configure IMAP settings");
  }
  const result = await res.json();
  invalidateIMAPCache();
  await getIMAPSettings(true);
  return result;
}

export async function disconnectIMAP(): Promise<any> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/settings/integrations/imap_email/disconnect`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to disconnect IMAP");
  }
  const result = await res.json();
  invalidateIMAPCache();
  await getIMAPSettings(true);
  return result;
}

export interface InvoiceVendorStatusResponse {
  invoice_id: string;
  is_zoho_connected: boolean;
  match_status: "MATCHED" | "NOT_FOUND" | "MISMATCH" | "NOT_CONNECTED";
  invoice_vendor: {
    vendor_name?: string | null;
    vendor_gstin?: string | null;
    vendor_pan?: string | null;
    vendor_address?: string | null;
    vendor_phone?: string | null;
    vendor_email?: string | null;
  };
  matched_vendor?: {
    contact_id?: string | null;
    contact_name?: string | null;
    gst_no?: string | null;
    pan_no?: string | null;
    email?: string | null;
    phone?: string | null;
  } | null;
  requires_action: boolean;
}

export async function getInvoiceVendorStatus(invoiceId: string): Promise<InvoiceVendorStatusResponse> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/vendor/status`, {
    headers: authHeaders,
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to check vendor status");
  }
  return res.json();
}

export async function addVendorToZoho(invoiceId: string): Promise<{
  status: string;
  message: string;
  contact_id: string;
  vendor: any;
}> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/vendor/add-to-zoho`, {
    method: "POST",
    headers: authHeaders,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to add vendor to Zoho Books");
  }
  return res.json();
}




export async function getHitlExtraction(invoiceId: string) {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/hitl/extraction`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch HITL extraction");
  return res.json();
}

export async function approveHitlExtraction(
  invoiceId: string,
  correctedData: any,
  postingDate?: string | null,
  periodResolution?: string | null,
  periodResolutionReason?: string | null
) {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/hitl/extraction/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({
      corrected_data: correctedData,
      posting_date: postingDate,
      period_resolution: periodResolution,
      period_resolution_reason: periodResolutionReason,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve HITL extraction");
  }
  return res.json();
}

export async function resolvePeriod(
  invoiceId: string,
  decision: "POST_TO_OPEN_PERIOD" | "PRIOR_PERIOD_EXCEPTION" | "FLAGGED_FOR_AUDIT",
  postingDate?: string | null,
  reason?: string | null
) {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/period-resolution`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({
      decision,
      posting_date: postingDate,
      reason,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to resolve accounting period");
  }
  return res.json();
}

export async function getTenantClosedPeriod() {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/tenants/closed-period`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch tenant closed period");
  return res.json();
}

export async function updateTenantClosedPeriod(booksClosedThroughDate: string | null) {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/tenants/closed-period`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ books_closed_through_date: booksClosedThroughDate }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update tenant closed period");
  }
  return res.json();
}

export async function getHitlFinal(invoiceId: string) {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/hitl/final`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch final HITL data");
  return res.json();
}

export async function approveHitlFinal(
  invoiceId: string,
  finalAccounting: any,
  finalJournal: any,
  postingDate?: string | null,
  periodResolution?: string | null,
  periodResolutionReason?: string | null
) {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/hitl/final/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({
      final_accounting: finalAccounting,
      final_journal: finalJournal,
      posting_date: postingDate,
      period_resolution: periodResolution,
      period_resolution_reason: periodResolutionReason,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve final HITL");
  }
  return res.json();
}

export async function getHitlHistory() {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/hitl/history`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch HITL history");
  return res.json();
}

export async function getInvoiceHitlHistory(invoiceId: string) {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/hitl/history`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch invoice HITL history");
  return res.json();
}

export async function matchZohoCOA(payload: {
  account_name?: string;
  account_type?: string;
  account_code?: string;
  zoho_account_id?: string;
}) {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/zoho/chart_of_accounts/match`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to match Zoho Chart of Accounts");
  return res.json();
}

export async function createZohoCOA(payload: {
  account_name: string;
  account_type?: string;
  account_code?: string;
  description?: string;
}) {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/zoho/chart_of_accounts/create`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to create Chart of Account in Zoho");
  }
  return res.json();
}

export async function assignInvoiceCOA(
  invoiceId: string,
  payload: {
    zoho_account_id: string;
    account_name: string;
    account_type?: string;
    account_code?: string;
    line_item_index?: number;
  }
) {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/assign_coa`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to assign Chart of Account to invoice");
  return res.json();
}

// ============================================================================
// Admin & User Access Management API
// ============================================================================

export interface UserManagementItem {
  id: string;
  email: string;
  full_name?: string | null;
  role: string;
  is_active: boolean;
  must_change_password?: boolean;
  created_at: string;
}

export interface CreateUserRequest {
  email: string;
  full_name?: string;
  role?: string;
}

export interface CreateUserActionResponse {
  success: boolean;
  message: string;
  user: UserManagementItem;
  temporary_password: string;
}

export interface UserInvitationItem {
  id: string;
  email: string;
  role: string;
  status: "PENDING" | "ACCEPTED" | "EXPIRED" | "REVOKED" | string;
  expires_at: string;
  created_at: string;
  accepted_at?: string | null;
  invitation_url?: string | null;
}

export interface InviteUserRequest {
  email: string;
  full_name?: string;
  role?: string;
}

export interface InviteActionResponse {
  success: boolean;
  email_sent: boolean;
  message: string;
  invitation: UserInvitationItem;
  invitation_url: string;
}

export interface AcceptInviteRequest {
  token: string;
  password: string;
  full_name?: string;
}

export interface ValidateInviteResponse {
  email: string;
  masked_email: string;
  role: string;
  tenant_id: string;
  status: string;
  otp_verified?: boolean;
  otp_sent?: boolean;
}

export interface SendInviteOtpResponse {
  success: boolean;
  email_sent: boolean;
  message: string;
  masked_email: string;
}

export interface VerifyInviteOtpResponse {
  success: boolean;
  message: string;
  email_verified: boolean;
}

export async function getUsers(): Promise<UserManagementItem[]> {
  const token = localStorage.getItem("token") || localStorage.getItem("dev_auth_token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/admin/users`, { headers });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to load users");
  }
  return res.json();
}

export async function createUser(data: CreateUserRequest): Promise<CreateUserActionResponse> {
  const token = localStorage.getItem("token") || localStorage.getItem("dev_auth_token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/admin/users`, {
    method: "POST",
    headers,
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to create user account");
  }
  return res.json();
}

export async function changePassword(newPassword: string) {
  const token = localStorage.getItem("token") || localStorage.getItem("dev_auth_token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/auth/change-password`, {
    method: "POST",
    headers,
    body: JSON.stringify({ new_password: newPassword }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to update password");
  }
  return res.json();
}

export async function getInvitations(): Promise<UserInvitationItem[]> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/admin/invitations`, { headers });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to load invitations");
  }
  return res.json();
}

export async function inviteUser(data: InviteUserRequest): Promise<InviteActionResponse> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/admin/invitations`, {
    method: "POST",
    headers,
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to send invitation");
  }
  return res.json();
}

export async function resendInvitation(invitationId: string): Promise<InviteActionResponse> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/admin/invitations/${invitationId}/resend`, {
    method: "POST",
    headers,
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to resend invitation");
  }
  return res.json();
}

export async function revokeInvitation(invitationId: string) {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/admin/invitations/${invitationId}/revoke`, {
    method: "POST",
    headers,
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to revoke invitation");
  }
  return res.json();
}

export async function deactivateUser(userId: string) {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/admin/users/${userId}/deactivate`, {
    method: "PATCH",
    headers,
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to deactivate user");
  }
  return res.json();
}

export async function reactivateUser(userId: string) {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && token !== "null") headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/admin/users/${userId}/reactivate`, {
    method: "PATCH",
    headers,
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to reactivate user");
  }
  return res.json();
}

export async function validateInvitationToken(invitationToken: string): Promise<ValidateInviteResponse> {
  const res = await fetch(`${API_BASE}/auth/accept-invite/validate?token=${encodeURIComponent(invitationToken)}`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Invalid or expired invitation token");
  }
  return res.json();
}

export async function sendInviteOtp(token: string): Promise<SendInviteOtpResponse> {
  const res = await fetch(`${API_BASE}/auth/accept-invite/send-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to send verification code");
  }
  return res.json();
}

export async function verifyInviteOtp(token: string, otp: string): Promise<VerifyInviteOtpResponse> {
  const res = await fetch(`${API_BASE}/auth/accept-invite/verify-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, otp }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Verification failed");
  }
  return res.json();
}

export async function acceptInvitation(data: AcceptInviteRequest) {
  const res = await fetch(`${API_BASE}/auth/accept-invite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to accept invitation");
  }
  return res.json();
}




