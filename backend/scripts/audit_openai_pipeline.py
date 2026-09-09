"""
Audit Script for OpenAI-only Invoice Processing Pipeline.
Queries live Supabase PostgreSQL DB and produces a comprehensive JSON audit dump.
Strictly read-only. No AI inference calls. No mock data.
"""
import os
import json
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('backend/.env')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def run_audit():
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError("DATABASE_URL not found in backend/.env")
    clean_url = url.replace('postgresql+psycopg2://', 'postgresql://')
    
    conn = psycopg2.connect(clean_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Total counts
    cur.execute("SELECT count(*) as total FROM invoices;")
    total_invoices = cur.fetchone()['total']
    
    cur.execute("SELECT count(*) as total FROM invoices WHERE raw_vlm_output IS NOT NULL;")
    total_with_vlm = cur.fetchone()['total']

    cur.execute("SELECT count(*) as total FROM invoices WHERE accounting_output IS NOT NULL;")
    total_with_acc = cur.fetchone()['total']

    cur.execute("SELECT count(*) as total FROM hitl_reviews;")
    total_hitl_reviews = cur.fetchone()['total']

    cur.execute("SELECT count(*) as total FROM audit_logs;")
    total_audit_logs = cur.fetchone()['total']

    cur.execute("SELECT count(*) as total FROM journal_entries;")
    total_journal_entries = cur.fetchone()['total']
    
    # 2. Invoices with VLM output details
    cur.execute("""
        SELECT 
            id, tenant_id, user_id, file_path, file_name, file_size, mime_type, file_hash,
            status, accounting_status, approval_status, export_status,
            invoice_type, zoho_bill_id, zoho_bill_number, exported_at, locked_at,
            period_category, period_decision, error_message, confidence_score, accounting_confidence,
            raw_vlm_output, current_vlm_output, accounting_output, current_accounting_output,
            gst_result, itc_result, financial_validation_result, journal_entry,
            financial_relevance, document_type, classification_confidence, classification_reason,
            created_at, updated_at
        FROM invoices 
        WHERE raw_vlm_output IS NOT NULL
        ORDER BY created_at DESC;
    """)
    invoices = cur.fetchall()

    # 3. Hitl reviews
    cur.execute("""
        SELECT id, invoice_id, stage, reviewer_id, status, input_snapshot, corrected_output, changes, created_at, approved_at
        FROM hitl_reviews
        ORDER BY created_at DESC;
    """)
    hitl_reviews = cur.fetchall()

    # 4. Audit logs
    cur.execute("""
        SELECT id, tenant_id, invoice_id, user_email, action, field_name, before_value, after_value, reason, created_at
        FROM audit_logs
        ORDER BY created_at DESC;
    """)
    audit_logs = cur.fetchall()

    # 5. Journal entries
    cur.execute("""
        SELECT id, invoice_id, entry_date, total_debit, total_credit, difference, balanced, is_balanced, status, created_at
        FROM journal_entries
        ORDER BY created_at DESC;
    """)
    journal_entries = cur.fetchall()

    # 6. Chart of Accounts table (for reference)
    cur.execute("""
        SELECT id, account_code, account_name, account_type, is_active FROM chart_of_accounts;
    """)
    coa_master = cur.fetchall()

    # 7. Vendors table (for reference)
    cur.execute("""
        SELECT id, vendor_name, gstin, pan, approval_status FROM vendors;
    """)
    vendors_master = cur.fetchall()

    cur.close()
    conn.close()

    return {
        "summary": {
            "total_invoices": total_invoices,
            "total_with_vlm": total_with_vlm,
            "total_with_acc": total_with_acc,
            "total_hitl_reviews": total_hitl_reviews,
            "total_audit_logs": total_audit_logs,
            "total_journal_entries": total_journal_entries,
            "total_coa_master": len(coa_master),
            "total_vendors_master": len(vendors_master)
        },
        "invoices": invoices,
        "hitl_reviews": hitl_reviews,
        "audit_logs": audit_logs,
        "journal_entries": journal_entries,
        "coa_master": coa_master,
        "vendors_master": vendors_master
    }

if __name__ == '__main__':
    data = run_audit()
    print("Fetched DB data successfully.")
    print("Summary:", data["summary"])
    
    # Save to scratch for analysis
    os.makedirs('backend/scratch', exist_ok=True)
    with open('backend/scratch/db_audit_dump.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    print("Saved raw audit dump to backend/scratch/db_audit_dump.json")
