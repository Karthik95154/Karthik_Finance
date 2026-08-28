export interface LineItem {
  description?: string | null;
  hsn_code?: string | null;
  quantity?: number | null;
  unit_price?: number | null;
  discount?: number | null;
  taxable_amount?: number | null;
  cgst_rate?: number | null;
  cgst_amount?: number | null;
  sgst_rate?: number | null;
  sgst_amount?: number | null;
  igst_rate?: number | null;
  igst_amount?: number | null;
  total?: number | null;
}

export interface BankDetails {
  account_holder_name?: string | null;
  account_number?: string | null;
  ifsc_code?: string | null;
  bank_name?: string | null;
  branch?: string | null;
  upi_id?: string | null;
}

export interface ExtractedInvoiceData {
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

  payment_terms?: string | null;
  bank_details?: BankDetails | null;

  line_items?: LineItem[];

  subtotal?: number | null;
  discount_total?: number | null;
  tax_total?: number | null;
  cgst?: number | null;
  cgst_amount?: number | null;
  sgst?: number | null;
  sgst_amount?: number | null;
  igst?: number | null;
  igst_amount?: number | null;
  shipping_charges?: number | null;
  other_charges?: number | null;
  round_off?: number | null;
  total_amount?: number | null;
  currency?: string | null;

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
  tds_type?: string | null;
  nature_of_payment?: string | null;
  tds_provision?: string | null;
  tds_section?: string | null;
  tds_rate?: number | null;
  rate_source?: string | null;
  tds_base_amount?: number | null;
  base_source?: string | null;
  extracted_tds_amount?: number | null;
  calculated_tds_amount?: number | null;
  calculation?: string | null;
  confidence?: number | null;
  needs_review?: boolean | null;
  reason?: string | null;
}

export interface AccountingOutput {
  accounting?: AccountingLineItem[];
  tds?: TdsResult | null;
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
  itc_status: "ELIGIBLE" | "INELIGIBLE" | "REVIEW_REQUIRED" | string;
  eligible_amount: number;
  ineligible_amount: number;
  reason: string;
  rule_reference: string;
}

export interface ItcResult {
  status: "ELIGIBLE" | "INELIGIBLE" | "REVIEW_REQUIRED" | string;
  eligible_amount: number;
  ineligible_amount: number;
  total_tax_amount: number;
  is_reverse_charge?: boolean;
  reason: string;
  rule_reference: string;
  line_item_breakdown?: ItcLineItemBreakdown[];
}

export interface FinancialCheck {
  name: string;
  description: string;
  status: "PASSED" | "MISMATCH" | "REVIEW_REQUIRED" | "NOT_APPLICABLE" | string;
  source_value?: number | null;
  calculated_value?: number | null;
  difference?: number | null;
  note?: string;
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
}

export interface JournalValidation {
  balanced: boolean;
  tolerance: number;
  errors: string[];
  warnings: string[];
}

export interface JournalEntry {
  status: "BALANCED" | "REVIEW_REQUIRED" | "UNBALANCED" | string;
  total_debit: number;
  total_credit: number;
  difference: number;
  currency: string;
  lines: JournalLine[];
  validation: JournalValidation;
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
  zoho_bill_id?: string | null;
  zoho_bill_number?: string | null;
  error_message?: string | null;
  confidence_score?: number | null;
  accounting_confidence?: number | null;
  raw_vlm_output?: RawVlmOutput | null;
  current_vlm_output?: RawVlmOutput | null;
  accounting_output?: AccountingOutput | null;
  current_accounting_output?: AccountingOutput | null;
  gst_result?: GstResult | null;
  itc_result?: ItcResult | null;
  financial_validation_result?: FinancialValidationResult | null;
  journal_entry?: JournalEntry | null;
  created_at: string;
  updated_at: string;
}

export interface InvoiceStatus {
  invoice_id: string;
  status: "PENDING" | "PROCESSING_VLM" | "PROCESSING_ACCOUNTING" | "COMPLETED" | "FAILED" | string;
  accounting_status?: string | null;
  error_message?: string | null;
  confidence_score?: number | null;
  accounting_confidence?: number | null;
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

export interface HealthResponse {
  status: string;
  project: string;
  database: string;
  storage: string;
  colab_vlm?: string;
  timestamp: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export async function uploadInvoice(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/invoices/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
  }

  return res.json();
}

export async function getInvoiceStatus(id: string): Promise<InvoiceStatus> {
  const res = await fetch(`${API_BASE}/invoices/${id}/status`, {
    cache: "no-store",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch status for invoice ${id}`);
  }

  return res.json();
}

export async function listInvoices(): Promise<InvoiceListItem[]> {
  const res = await fetch(`${API_BASE}/invoices`, {
    cache: "no-store",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to fetch invoices list");
  }

  return res.json();
}

export async function getInvoice(id: string): Promise<Invoice> {
  const res = await fetch(`${API_BASE}/invoices/${id}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch invoice ${id}`);
  }

  return res.json();
}

export async function triggerAccountingCategorization(id: string): Promise<InvoiceStatus> {
  const res = await fetch(`${API_BASE}/invoices/${id}/categorize`, {
    method: "POST",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to trigger accounting for invoice ${id}`);
  }

  return res.json();
}

export async function updateInvoiceExtraction(
  id: string,
  currentVlmOutput?: RawVlmOutput | null,
  currentAccountingOutput?: AccountingOutput | null
): Promise<Invoice> {
  const body: Record<string, any> = {};
  if (currentVlmOutput !== undefined) body.current_vlm_output = currentVlmOutput;
  if (currentAccountingOutput !== undefined) body.current_accounting_output = currentAccountingOutput;

  const res = await fetch(`${API_BASE}/invoices/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to update invoice ${id}`);
  }

  return res.json();
}

export function getInvoiceFileUrl(id: string): string {
  return `${API_BASE}/invoices/${id}/file`;
}

export async function getInvoiceJournal(id: string): Promise<JournalEntry> {
  const res = await fetch(`${API_BASE}/invoices/${id}/journal`, {
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

export async function getAuthHeaders(): Promise<Record<string, string>> {
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem("dev_auth_token");
    if (stored) {
      return { Authorization: `Bearer ${stored}` };
    }
  }
  if (!devToken) {
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

export async function getZohoStatus(): Promise<ZohoStatusResponse> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/zoho/status`, {
    headers: authHeaders,
    cache: "no-store",
  });
  if (!res.ok) {
    return { connected: false, status: "DISCONNECTED" };
  }
  return res.json();
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
  return res.json();
}

export async function selectZohoOrganization(organizationId: string, organizationName?: string): Promise<{ success: boolean; message: string; accounts_synced?: number; taxes_synced?: number; vendors_synced?: number }> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/zoho/select-organization`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ organization_id: organizationId, organization_name: organizationName }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to select Zoho organization");
  }
  return res.json();
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
  return res.json();
}

export async function getMasterDataSummary(): Promise<ZohoMasterDataSummary> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/zoho/master-data-summary`, {
    headers: authHeaders,
    cache: "no-store",
  });
  if (!res.ok) {
    return { chart_of_accounts_count: 0, tax_rates_count: 0, vendors_count: 0 };
  }
  return res.json();
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
  return res.json();
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

