"""
Comprehensive Audit Engine for 33 Persisted OpenAI Invoices.
Inspects:
- 13 Top-Level Contract Sections
- Nested extraction fields
- Model vs Backend vs HITL traces
- TDS proposals vs Engine calculations
- COA proposals vs Master accounts
- Audit logs & HITL corrections
"""
import json
import os
from collections import defaultdict, Counter

def run_comprehensive_audit():
    with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    invoices = data['invoices']
    hitl_reviews = data['hitl_reviews']
    audit_logs = data['audit_logs']
    journal_entries = data['journal_entries']
    coa_master = {c['id']: c for c in data['coa_master']}
    coa_by_name = {c['account_name'].lower(): c for c in data['coa_master']}

    print(f"Total invoices: {len(invoices)}")

    # 1. Inspect Top-Level Keys in raw_vlm_output
    # The 13 required top-level contract keys:
    CONTRACT_SECTIONS = [
        "invoice_details",
        "vendor_details",
        "customer_details",
        "line_items",
        "financial_details",
        "gst_support",
        "tds_support",
        "tcs_support",
        "itc_support",
        "coa_support",
        "gl_support",
        "validation",
        "review_flags"
    ]

    section_stats = {sec: {"present": 0, "non_empty": 0, "dict_or_list": 0} for sec in CONTRACT_SECTIONS}
    extra_top_level_keys = Counter()

    # Detailed fields inside sections
    FIELDS_TO_TRACK = {
        # invoice_details
        "invoice_number": ("invoice_details", "invoice_number"),
        "invoice_date": ("invoice_details", "invoice_date"),
        "due_date": ("invoice_details", "due_date"),
        "po_number": ("invoice_details", "po_number"),
        "place_of_supply": ("invoice_details", "place_of_supply"),
        "payment_terms": ("invoice_details", "payment_terms"),
        "currency": ("invoice_details", "currency"),
        "document_type": ("invoice_details", "document_type"),
        # vendor_details
        "vendor_name": ("vendor_details", "vendor_name"),
        "vendor_address": ("vendor_details", "vendor_address"),
        "vendor_gstin": ("vendor_details", "vendor_gstin"),
        "vendor_pan": ("vendor_details", "vendor_pan"),
        "vendor_phone": ("vendor_details", "vendor_phone"),
        "vendor_email": ("vendor_details", "vendor_email"),
        "bank_account_holder": ("vendor_details.bank_details", "account_holder_name"),
        "bank_name": ("vendor_details.bank_details", "bank_name"),
        "bank_account_number": ("vendor_details.bank_details", "account_number"),
        "bank_ifsc": ("vendor_details.bank_details", "ifsc_code"),
        "bank_branch": ("vendor_details.bank_details", "branch"),
        "bank_address": ("vendor_details.bank_details", "address"),
        "bank_upi": ("vendor_details.bank_details", "upi_id_vpa"),
        # customer_details
        "customer_name": ("customer_details", "customer_name"),
        "customer_address": ("customer_details", "customer_address"),
        "customer_gstin": ("customer_details", "customer_gstin"),
        "customer_pan": ("customer_details", "customer_pan"),
        "customer_phone": ("customer_details", "customer_phone"),
        "customer_email": ("customer_details", "customer_email"),
        # financial_details
        "subtotal": ("financial_details", "subtotal"),
        "discount_total": ("financial_details", "discount_total"),
        "taxable_amount": ("financial_details", "taxable_amount"),
        "tax_total": ("financial_details", "tax_total"),
        "cgst_amount": ("financial_details", "cgst_amount"),
        "sgst_amount": ("financial_details", "sgst_amount"),
        "igst_amount": ("financial_details", "igst_amount"),
        "round_off": ("financial_details", "round_off"),
        "total_amount": ("financial_details", "total_amount"),
        # gst_support
        "supply_type_candidate": ("gst_support", "supply_type_candidate"),
        "tax_components_candidate": ("gst_support", "tax_components_candidate"),
        "rcm_candidate": ("gst_support", "rcm_candidate"),
        # tds_support
        "tds_applicable_candidate": ("tds_support", "tds_applicable_candidate"),
        "tds_payment_nature": ("tds_support", "payment_nature"),
        "tds_law_version_candidate": ("tds_support", "law_version_candidate"),
        "tds_provision_candidate": ("tds_support", "provision_candidate"),
        "tds_legacy_provision": ("tds_support", "legacy_provision_reference"),
        "tds_rate_candidate": ("tds_support", "rate_candidate"),
        "tds_base_candidate": ("tds_support", "base_candidate"),
        "tds_threshold_status": ("tds_support", "threshold_status"),
        "tds_pan_status": ("tds_support", "pan_status"),
        # itc_support
        "itc_candidate": ("itc_support", "candidate"),
        "itc_business_use": ("itc_support", "business_use"),
        "itc_document_sufficiency": ("itc_support", "document_sufficiency"),
        "itc_gstr2b_status": ("itc_support", "gstr2b_status"),
        "itc_blocked_credit_risk": ("itc_support", "blocked_credit_risk"),
        "itc_eligible_amount_candidate": ("itc_support", "eligible_amount_candidate"),
    }

    field_stats = {
        k: {"present": 0, "non_null": 0, "values_counter": Counter()}
        for k in FIELDS_TO_TRACK
    }

    line_item_field_stats = {
        "description": 0, "quantity": 0, "unit": 0, "unit_price": 0,
        "discount": 0, "taxable_amount": 0, "hsn_sac": 0, "gst_rate": 0,
        "cgst_amount": 0, "sgst_amount": 0, "igst_amount": 0
    }
    total_line_items = 0

    # Invoice specific audits
    invoice_audits = []

    # TDS performance tracking
    tds_evaluations = []
    # COA performance tracking
    coa_evaluations = []

    for inv in invoices:
        raw = inv.get("raw_vlm_output") or {}
        curr_vlm = inv.get("current_vlm_output") or {}
        acc = inv.get("accounting_output") or {}
        curr_acc = inv.get("current_accounting_output") or {}
        je = inv.get("journal_entry") or {}
        inv_id = str(inv["id"])

        # Determine root of raw_vlm_output
        root = raw
        if isinstance(root.get("prediction"), dict):
            root = root["prediction"]
        elif isinstance(root.get("data"), dict) and any(k in root["data"] for k in ("invoice_details", "vendor_details")):
            root = root["data"]

        # 1. Section presence
        for sec in CONTRACT_SECTIONS:
            if sec in root:
                section_stats[sec]["present"] += 1
                val = root[sec]
                if val is not None and len(val) > 0:
                    section_stats[sec]["non_empty"] += 1
                if isinstance(val, (dict, list)):
                    section_stats[sec]["dict_or_list"] += 1

        for k in root.keys():
            if k not in CONTRACT_SECTIONS:
                extra_top_level_keys[k] += 1

        # 2. Field presence & values
        for f_key, (sec_path, f_name) in FIELDS_TO_TRACK.items():
            sec_obj = root
            for part in sec_path.split("."):
                if isinstance(sec_obj, dict):
                    sec_obj = sec_obj.get(part)
                else:
                    sec_obj = None
            if isinstance(sec_obj, dict) and f_name in sec_obj:
                field_stats[f_key]["present"] += 1
                val = sec_obj[f_name]
                if val is not None:
                    field_stats[f_key]["non_null"] += 1
                    # Store string representation of value for distribution
                    str_v = str(val) if not isinstance(val, (list, dict)) else f"[{type(val).__name__}]"
                    field_stats[f_key]["values_counter"][str_v[:40]] += 1

        # 3. Line items audit
        items = root.get("line_items") or []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    total_line_items += 1
                    for lk in line_item_field_stats:
                        if item.get(lk) is not None:
                            line_item_field_stats[lk] += 1

        # 4. TDS Audit
        tds_supp = root.get("tds_support") or {}
        tds_app_raw = tds_supp.get("tds_applicable_candidate") if isinstance(tds_supp, dict) else None
        tds_sec_raw = tds_supp.get("provision_candidate") if isinstance(tds_supp, dict) else None
        tds_rate_raw = tds_supp.get("rate_candidate") if isinstance(tds_supp, dict) else None
        tds_base_raw = tds_supp.get("base_candidate") if isinstance(tds_supp, dict) else None
        tds_nature_raw = tds_supp.get("payment_nature") if isinstance(tds_supp, dict) else None
        tds_status_raw = tds_supp.get("threshold_status") if isinstance(tds_supp, dict) else None

        # Backend TDS output
        backend_tds = None
        if isinstance(acc, dict):
            backend_tds = acc.get("tds") or acc.get("tds_assessment")
        if not backend_tds and isinstance(curr_acc, dict):
            backend_tds = curr_acc.get("tds") or curr_acc.get("tds_assessment")

        # Journal TDS lines
        je_tds_lines = []
        if isinstance(je, dict):
            for line in je.get("lines", []):
                if line.get("line_type") == "TDS_PAYABLE":
                    je_tds_lines.append(line)

        # Check HITL review for this invoice
        inv_hitl = [h for h in hitl_reviews if str(h.get("invoice_id")) == inv_id]
        inv_audits = [a for a in audit_logs if str(a.get("invoice_id")) == inv_id]

        tds_eval = {
            "invoice_id": inv_id,
            "file_name": inv.get("file_name"),
            "model_tds": {
                "applicable": tds_app_raw,
                "section": tds_sec_raw,
                "rate": tds_rate_raw,
                "base": tds_base_raw,
                "nature": tds_nature_raw,
                "threshold_status": tds_status_raw
            },
            "backend_tds": backend_tds,
            "journal_tds_lines": je_tds_lines,
            "has_hitl": len(inv_hitl) > 0,
            "audit_logs": [a.get("action") for a in inv_audits]
        }
        tds_evaluations.append(tds_eval)

        # 5. COA Audit
        coa_supp = root.get("coa_support") or {}
        line_matches = coa_supp.get("line_matches") or [] if isinstance(coa_supp, dict) else []
        backend_acc_lines = acc.get("accounting") or [] if isinstance(acc, dict) else []
        
        coa_eval = {
            "invoice_id": inv_id,
            "file_name": inv.get("file_name"),
            "model_line_matches": line_matches,
            "backend_accounting_lines": backend_acc_lines,
            "journal_lines": je.get("lines") if isinstance(je, dict) else []
        }
        coa_evaluations.append(coa_eval)

        # 6. Overall invoice record
        invoice_audits.append({
            "id": inv_id,
            "file_name": inv.get("file_name"),
            "status": inv.get("status"),
            "accounting_status": inv.get("accounting_status"),
            "approval_status": inv.get("approval_status"),
            "export_status": inv.get("export_status"),
            "confidence_score": inv.get("confidence_score"),
            "accounting_confidence": inv.get("accounting_confidence"),
            "invoice_number": (root.get("invoice_details") or {}).get("invoice_number"),
            "vendor_name": (root.get("vendor_details") or {}).get("vendor_name"),
            "total_amount": (root.get("financial_details") or {}).get("total_amount"),
            "line_items_count": len(items) if isinstance(items, list) else 0,
            "hitl_reviews_count": len(inv_hitl),
            "audit_logs_count": len(inv_audits),
        })

    out = {
        "total_invoices": len(invoices),
        "contract_sections_stats": section_stats,
        "extra_top_level_keys": dict(extra_top_level_keys),
        "fields_stats": {
            k: {
                "present": v["present"],
                "present_pct": round(v["present"] / len(invoices) * 100, 1),
                "non_null": v["non_null"],
                "non_null_pct": round(v["non_null"] / len(invoices) * 100, 1),
                "top_values": dict(v["values_counter"].most_common(5))
            }
            for k, v in field_stats.items()
        },
        "line_items_stats": {
            "total_line_items": total_line_items,
            "field_population": {
                k: {
                    "count": cnt,
                    "pct": round(cnt / total_line_items * 100, 1) if total_line_items > 0 else 0
                }
                for k, cnt in line_item_field_stats.items()
            }
        },
        "tds_evaluations": tds_evaluations,
        "coa_evaluations": coa_evaluations,
        "invoice_audits": invoice_audits
    }

    with open('backend/scratch/comprehensive_audit_results.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, default=str)

    print("Comprehensive audit complete. Saved to backend/scratch/comprehensive_audit_results.json")

if __name__ == '__main__':
    run_comprehensive_audit()
