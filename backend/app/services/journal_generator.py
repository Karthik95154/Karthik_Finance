import logging
from typing import Any, Dict, List, Optional
from app.services.financial_validator import financial_validator
from app.services.tds_engine import tds_engine

logger = logging.getLogger(__name__)


class JournalGenerator:
    """
    Generates balanced double-entry General Ledger journal entries from
    extracted invoice data, Finance-approved Chart of Accounts, and TDS calculations.
    """

    @classmethod
    def generate_journal_entry(
        cls,
        invoice_data: Dict[str, Any],
        accounting_data: Optional[Dict[str, Any]] = None,
        cost_center: Optional[str] = None,
        project: Optional[str] = None,
        department: Optional[str] = None,
        require_approved: bool = False,
    ) -> Dict[str, Any]:
        """
        Builds balanced Debit / Credit lines:
        [DR] Line-item Expense Accounts (by taxable amount)
        [DR] Input CGST (if intra-state)
        [DR] Input SGST (if intra-state)
        [DR] Input IGST (if inter-state)
        [CR] TDS Payable (if TDS applicable)
        [CR] Accounts Payable - Vendor (Net Payable Amount)

        CRITICAL ARCHITECTURAL CONSTRAINT:
        When require_approved=True:
        - Every line item MUST have explicit approved_account_id and approved_account_name.
        - ZERO FALLBACK to ai_account_id is permitted for authoritative journals.
        """
        lines: List[Dict[str, Any]] = []
        line_num = 1

        vendor_name = invoice_data.get("vendor_name") or "Vendor"
        vendor_gstin = invoice_data.get("vendor_gstin")
        customer_gstin = invoice_data.get("customer_gstin")
        vendor_pan = invoice_data.get("vendor_pan")
        place_of_supply = invoice_data.get("place_of_supply")
        invoice_date = invoice_data.get("invoice_date")

        total_amount = float(invoice_data.get("total_amount") or 0.0)
        subtotal = float(invoice_data.get("subtotal") or 0.0)

        # 1. Determine Supply Type (Intra vs Inter state)
        supply_type = financial_validator.determine_supply_type(
            vendor_gstin=vendor_gstin,
            customer_gstin=customer_gstin,
            place_of_supply=place_of_supply,
        )

        # 2. Extract line item accounts from accounting_data
        ai_accounting = []
        if accounting_data and isinstance(accounting_data, dict):
            ai_accounting = accounting_data.get("accounting") or []

        account_map = {}
        has_unapproved_lines = False

        # Index accounting lines by line_index
        for item in ai_accounting:
            idx = item.get("line_index", 1)
            approved_id = item.get("approved_account_id") or item.get("final_account_id")
            approved_name = item.get("approved_account_name") or item.get("final_account_name")
            ai_id = item.get("ai_account_id")
            ai_name = item.get("ai_account_name")

            if require_approved:
                # ZERO FALLBACK: Authoritative journals require explicit Finance approval
                if not approved_id or not approved_name:
                    raise ValueError(
                        f"Cannot generate authoritative journal: Line item {idx} has not been approved by Finance. "
                        f"approved_account_id and approved_account_name are required."
                    )
                account_map[idx] = (approved_id, approved_name, True)
            else:
                # Pre-approval preview mode: clearly identify unapproved suggestions
                if approved_id and approved_name:
                    account_map[idx] = (approved_id, approved_name, True)
                elif ai_name:
                    has_unapproved_lines = True
                    account_map[idx] = (ai_id, f"[Unapproved] {ai_name}", False)
                else:
                    has_unapproved_lines = True
                    account_map[idx] = (None, f"[Unapproved] Line {idx} Expense", False)

        # 3. Add Expense Line Items (DEBIT)
        line_items = invoice_data.get("line_items") or []

        line_cgst = sum(float(item.get("cgst_amount") or 0.0) for item in line_items)
        line_sgst = sum(float(item.get("sgst_amount") or 0.0) for item in line_items)
        line_igst = sum(float(item.get("igst_amount") or 0.0) for item in line_items)

        cgst_total = line_cgst if line_cgst > 0 else float(invoice_data.get("cgst_amount") or invoice_data.get("cgst") or 0.0)
        sgst_total = line_sgst if line_sgst > 0 else float(invoice_data.get("sgst_amount") or invoice_data.get("sgst") or 0.0)
        igst_total = line_igst if line_igst > 0 else float(invoice_data.get("igst_amount") or invoice_data.get("igst") or 0.0)

        # Fallback to header-level tax_total if individual GST components were not broken down
        if cgst_total == 0 and sgst_total == 0 and igst_total == 0:
            hdr_tax = float(invoice_data.get("tax_total") or invoice_data.get("total_tax") or 0.0)
            if hdr_tax <= 0 and total_amount > subtotal:
                hdr_tax = round(total_amount - subtotal, 2)
            
            if hdr_tax > 0:
                if supply_type == "INTRA_STATE":
                    cgst_total = round(hdr_tax / 2.0, 2)
                    sgst_total = round(hdr_tax - cgst_total, 2)
                else:
                    igst_total = round(hdr_tax, 2)

        if line_items:
            for idx, item in enumerate(line_items, 1):
                taxable = float(item.get("taxable_amount") or (float(item.get("quantity") or 1.0) * float(item.get("unit_price") or 0.0)))
                
                if idx in account_map:
                    acc_id, acc_name, is_app = account_map[idx]
                else:
                    if require_approved:
                        raise ValueError(f"Line item {idx} lacks Finance-approved Chart of Accounts.")
                    has_unapproved_lines = True
                    acc_id, acc_name, is_app = (None, f"[Unapproved] {item.get('description') or f'Expense {idx}'}", False)

                lines.append({
                    "line_number": line_num,
                    "account_id": acc_id,
                    "account_name": acc_name,
                    "is_approved": is_app,
                    "line_type": "DR",
                    "amount": round(taxable, 2),
                    "description": item.get("description") or f"Line {idx} Expense",
                    "cost_center": cost_center,
                    "project": project,
                    "department": department,
                })
                line_num += 1
        else:
            # Single aggregated line if no individual line items
            if 1 in account_map:
                acc_id, acc_name, is_app = account_map[1]
            else:
                if require_approved:
                    raise ValueError("Invoice lacks Finance-approved Chart of Accounts.")
                has_unapproved_lines = True
                acc_id, acc_name, is_app = (None, "[Unapproved] General Operating Expense", False)

            lines.append({
                "line_number": line_num,
                "account_id": acc_id,
                "account_name": acc_name,
                "is_approved": is_app,
                "line_type": "DR",
                "amount": round(subtotal or total_amount, 2),
                "description": "Invoice Expense",
                "cost_center": cost_center,
                "project": project,
                "department": department,
            })
            line_num += 1

        # 4. Add Tax Lines (DEBIT)
        if supply_type == "INTRA_STATE":
            if cgst_total > 0:
                lines.append({
                    "line_number": line_num,
                    "account_id": "INPUT_CGST",
                    "account_name": "Input CGST Receivable",
                    "is_approved": True,
                    "line_type": "DR",
                    "amount": round(cgst_total, 2),
                    "description": "Input Central GST",
                    "cost_center": cost_center,
                    "project": project,
                    "department": department,
                })
                line_num += 1

            if sgst_total > 0:
                lines.append({
                    "line_number": line_num,
                    "account_id": "INPUT_SGST",
                    "account_name": "Input SGST Receivable",
                    "is_approved": True,
                    "line_type": "DR",
                    "amount": round(sgst_total, 2),
                    "description": "Input State GST",
                    "cost_center": cost_center,
                    "project": project,
                    "department": department,
                })
                line_num += 1
        else:
            # INTER_STATE
            if igst_total > 0:
                lines.append({
                    "line_number": line_num,
                    "account_id": "INPUT_IGST",
                    "account_name": "Input IGST Receivable",
                    "is_approved": True,
                    "line_type": "DR",
                    "amount": round(igst_total, 2),
                    "description": "Input Integrated GST",
                    "cost_center": cost_center,
                    "project": project,
                    "department": department,
                })
                line_num += 1

        # 5. TDS Deduction (CREDIT)
        tds_info = (accounting_data or {}).get("tds") or {}
        tds_applicable = bool(tds_info.get("applicable"))
        tds_section = tds_info.get("tds_section") or "194C"
        tds_amount = float(tds_info.get("calculated_tds_amount") or 0.0)

        # Deterministic recalculation if missing
        if tds_applicable and tds_amount <= 0 and subtotal > 0:
            calc = tds_engine.calculate_tds(
                section=tds_section,
                base_amount=subtotal,
                vendor_pan=vendor_pan,
            )
            tds_amount = calc.get("tds_amount", 0.0)

        if tds_applicable and tds_amount > 0:
            lines.append({
                "line_number": line_num,
                "account_id": f"TDS_PAYABLE_{tds_section}",
                "account_name": f"TDS Payable (Sec {tds_section})",
                "is_approved": True,
                "line_type": "CR",
                "amount": round(tds_amount, 2),
                "description": f"TDS deduction on {vendor_name}",
                "cost_center": cost_center,
                "project": project,
                "department": department,
            })
            line_num += 1

        # 6. Accounts Payable - Vendor (CREDIT)
        net_payable = round(total_amount - tds_amount, 2)
        lines.append({
            "line_number": line_num,
            "account_id": "AP_VENDOR",
            "account_name": f"Accounts Payable - {vendor_name}",
            "is_approved": True,
            "line_type": "CR",
            "amount": net_payable,
            "description": f"Payable to {vendor_name}",
            "cost_center": cost_center,
            "project": project,
            "department": department,
        })

        # 7. Check Debits vs Credits balance & Penny Rounding Adjustment
        total_dr = round(sum(item["amount"] for item in lines if item["line_type"] == "DR"), 2)
        total_cr = round(sum(item["amount"] for item in lines if item["line_type"] == "CR"), 2)

        # Reconcile minor penny rounding difference (<= 1.0) with a Round Off balancing line
        diff = round(total_dr - total_cr, 2)
        if 0 < abs(diff) <= 1.0:
            if diff < 0:
                # Debits are less than Credits
                lines.append({
                    "line_number": line_num,
                    "account_id": "ROUND_OFF_EXPENSE",
                    "account_name": "Round Off Adjustment",
                    "is_approved": True,
                    "line_type": "DR",
                    "amount": round(abs(diff), 2),
                    "description": "Round Off Adjustment",
                    "cost_center": cost_center,
                    "project": project,
                    "department": department,
                })
            else:
                # Credits are less than Debits
                lines.append({
                    "line_number": line_num,
                    "account_id": "ROUND_OFF_INCOME",
                    "account_name": "Round Off Adjustment",
                    "is_approved": True,
                    "line_type": "CR",
                    "amount": round(abs(diff), 2),
                    "description": "Round Off Adjustment",
                    "cost_center": cost_center,
                    "project": project,
                    "department": department,
                })
            total_dr = round(sum(item["amount"] for item in lines if item["line_type"] == "DR"), 2)
            total_cr = round(sum(item["amount"] for item in lines if item["line_type"] == "CR"), 2)

        is_balanced = abs(total_dr - total_cr) <= 0.05

        return {
            "entry_date": invoice_date,
            "supply_type": supply_type,
            "total_debit": total_dr,
            "total_credit": total_cr,
            "is_balanced": is_balanced,
            "has_unapproved_lines": has_unapproved_lines,
            "difference": round(abs(total_dr - total_cr), 2),
            "lines": lines,
        }


journal_generator = JournalGenerator()
