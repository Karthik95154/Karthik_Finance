"""
Authoritative Double-Entry Accounting Journal Generator for Invoices.
Consumes upstream pipeline outputs:
- Effective Invoice Data (VLM extraction / HITL edits)
- Stage 3: Accounting Classification (COA, provenance, TDS metadata)
- Stage 4: GST Engine (supply_type, calculated and extracted taxes)
- Stage 4: ITC Engine (eligible_itc, blocked_itc, reversal_itc, review_amount, component breakdowns)
- Stage 5: Financial Validation (reconciliation, arithmetic mismatch gates)

Single Source of Truth for:
- UI Live Preview
- Approval Gate Validation
- invoice.journal_entry (JSONB)
- journal_entries & journal_lines (Relational Tables)
- Zoho Books Export Alignment
"""

import logging
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Standard Account IDs and Names for Taxes, Liabilities, and System Accounts
STANDARD_ACCOUNTS = {
    "INPUT_CGST": {
        "account_id": "TAX_INP_CGST",
        "account_name": "Input CGST",
        "account_type": "asset",
    },
    "INPUT_SGST": {
        "account_id": "TAX_INP_SGST",
        "account_name": "Input SGST / UTGST",
        "account_type": "asset",
    },
    "INPUT_IGST": {
        "account_id": "TAX_INP_IGST",
        "account_name": "Input IGST",
        "account_type": "asset",
    },
    "INPUT_CESS": {
        "account_id": "TAX_INP_CESS",
        "account_name": "Input Cess",
        "account_type": "asset",
    },
    "INELIGIBLE_TAX": {
        "account_id": "TAX_BLOCKED",
        "account_name": "Ineligible Input GST Expense",
        "account_type": "expense",
    },
    "ACCOUNTS_PAYABLE": {
        "account_id": "LIAB_AP",
        "account_name": "Accounts Payable (Vendor)",
        "account_type": "liability",
    },
    "TDS_PAYABLE": {
        "account_id": "LIAB_TDS_PAYABLE",
        "account_name": "TDS Payable",
        "account_type": "liability",
    },
    "SHIPPING_CHARGES": {
        "account_id": "ACC_12",
        "account_name": "Shipping & Freight Charges",
        "account_type": "expense",
    },
    "OTHER_CHARGES": {
        "account_id": "EXP_OTHER_CHARGES",
        "account_name": "Other Direct Expenses",
        "account_type": "expense",
    },
    "ROUND_OFF": {
        "account_id": "ROUND_OFF",
        "account_name": "Round Off Adjustment",
        "account_type": "expense",
    },
}

DEFAULT_TOLERANCE = 1.0  # 1 INR tolerance for monetary rounding


class JournalLine(BaseModel):
    account_id: Optional[str] = None
    account_name: str
    line_type: str = Field(
        ...,
        description="EXPENSE, ASSET, INPUT_TAX, TDS_PAYABLE, ACCOUNTS_PAYABLE, ROUND_OFF, OTHER, DR, CR",
    )
    debit: float = 0.0
    credit: float = 0.0
    amount: float = 0.0
    source_line_index: Optional[int] = None
    provenance: str = Field(
        default="DETERMINISTIC",
        description="AI_PREDICTED, HITL_OVERRIDE, DETERMINISTIC",
    )
    description: Optional[str] = None
    cost_center: Optional[str] = None
    project: Optional[str] = None
    department: Optional[str] = None
    rule_reference: Optional[str] = None


class JournalValidation(BaseModel):
    balanced: bool = False
    tolerance: float = DEFAULT_TOLERANCE
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class JournalEntryResult(BaseModel):
    status: str = Field(
        ...,
        description="BALANCED, REVIEW_REQUIRED, UNBALANCED",
    )
    total_debit: float = 0.0
    total_credit: float = 0.0
    difference: float = 0.0
    currency: str = "INR"
    lines: List[JournalLine] = Field(default_factory=list)
    validation: JournalValidation = Field(default_factory=JournalValidation)


class JournalGenerator:
    """
    Unified Authoritative Double-Entry Accounting Journal Generator for Invoices.
    """

    def __init__(self, tolerance: float = DEFAULT_TOLERANCE):
        self.tolerance = tolerance

    def generate_journal(
        self,
        invoice_data: Dict[str, Any],
        accounting_classification: Optional[Dict[str, Any]] = None,
        gst_result: Optional[Dict[str, Any]] = None,
        itc_result: Optional[Dict[str, Any]] = None,
        tds_result: Optional[Dict[str, Any]] = None,
        financial_validation_result: Optional[Dict[str, Any]] = None,
        cost_center: Optional[str] = None,
        project: Optional[str] = None,
        department: Optional[str] = None,
        require_approved: bool = False,
    ) -> Dict[str, Any]:
        """
        Single Authoritative Entrypoint for generating balanced double-entry General Ledger journals.
        Consumes validated pipeline outputs directly.
        """
        lines: List[JournalLine] = []
        errors: List[str] = []
        warnings: List[str] = []
        requires_review: bool = False

        # Extract underlying invoice payload if wrapped in {'data': ...}
        inv = invoice_data.get("data", invoice_data) if isinstance(invoice_data, dict) else {}

        # ----------------------------------------------------
        # 1. UPSTREAM GATES & VALIDATION STATUS CHECKS
        # ----------------------------------------------------
        if financial_validation_result:
            fin_status = financial_validation_result.get("overall_status")
            if fin_status == "MISMATCH":
                requires_review = True
                warnings.append(
                    "Stage 5 Financial Validation reported discrepancies. Journal set to REVIEW_REQUIRED."
                )
                if financial_validation_result.get("errors"):
                    warnings.extend(financial_validation_result["errors"])
            elif fin_status == "REVIEW_REQUIRED":
                requires_review = True
                warnings.append("Stage 5 Financial Validation requires review.")

        if gst_result:
            gst_val_status = gst_result.get("validation_status")
            if gst_val_status in ("GST_MISMATCH", "REVIEW_REQUIRED"):
                requires_review = True
                warnings.append(
                    f"Stage 4 GST Engine reported {gst_val_status}. Preserving validation alert in journal."
                )
                if gst_result.get("errors"):
                    warnings.extend(gst_result["errors"])

        # ----------------------------------------------------
        # 2. EXTRACT INVOICE TOTALS & AMOUNTS
        # ----------------------------------------------------
        subtotal = self._clean_num(inv.get("subtotal"))
        tax_total = self._clean_num(inv.get("tax_total") or inv.get("total_tax"))
        total_amount = self._clean_num(inv.get("total_amount"))
        discount = self._clean_num(inv.get("discount_total") or inv.get("discount")) or 0.0
        shipping = self._clean_num(inv.get("shipping_charges") or inv.get("shipping")) or 0.0
        other_charges = self._clean_num(inv.get("other_charges")) or 0.0
        round_off = self._clean_num(inv.get("round_off")) or 0.0
        vendor_name = inv.get("vendor_name") or "Vendor"

        line_items = inv.get("line_items") or []

        if total_amount is None and subtotal is None and not line_items:
            errors.append("Invoice lacks financial amounts to construct journal entry.")
            return JournalEntryResult(
                status="REVIEW_REQUIRED",
                total_debit=0.0,
                total_credit=0.0,
                difference=0.0,
                lines=[],
                validation=JournalValidation(
                    balanced=False,
                    tolerance=self.tolerance,
                    errors=errors,
                    warnings=warnings,
                ),
            ).model_dump()

        # ----------------------------------------------------
        # 3. LINE ITEM EXPENSE / ASSET DEBITS
        # ----------------------------------------------------
        accounting_list = []
        if accounting_classification:
            accounting_list = (
                accounting_classification.get("accounting")
                or accounting_classification.get("line_items")
                or []
            )

        acc_by_index: Dict[int, Dict[str, Any]] = {}
        for item in accounting_list:
            if isinstance(item, dict):
                idx = item.get("line_index")
                if idx is not None:
                    acc_by_index[idx] = item

        total_line_taxable_debits = 0.0

        if line_items:
            for idx, line in enumerate(line_items):
                desc = line.get("description") or f"Line {idx + 1}"
                taxable = self._clean_num(
                    line.get("taxable_amount")
                    or line.get("taxable")
                    or line.get("pretax_amount")
                    or line.get("total")
                    or line.get("amount")
                )
                if taxable is None:
                    qty = self._clean_num(line.get("quantity"))
                    price = self._clean_num(line.get("unit_price"))
                    line_disc = self._clean_num(line.get("discount") or line.get("discount_amount")) or 0.0
                    if qty is not None and price is not None:
                        taxable = round((qty * price) - line_disc, 2)
                    elif subtotal is not None and len(line_items) == 1:
                        taxable = subtotal
                    else:
                        taxable = 0.0

                # Match line in accounting by line_index or sequential index
                acc_info = {}
                if idx in acc_by_index:
                    acc_info = acc_by_index[idx]
                elif (idx + 1) in acc_by_index:
                    acc_info = acc_by_index[idx + 1]
                elif idx < len(accounting_list):
                    acc_info = accounting_list[idx]

                approved_acc_id = acc_info.get("approved_account_id") or acc_info.get("final_account_id")
                approved_acc_name = acc_info.get("approved_account_name") or acc_info.get("final_account_name")
                ai_acc_id = acc_info.get("ai_account_id") or acc_info.get("account_id")
                ai_acc_name = acc_info.get("ai_account_name") or acc_info.get("account_name")

                if approved_acc_id and approved_acc_name:
                    account_id = approved_acc_id
                    account_name = approved_acc_name
                    provenance = "HITL_OVERRIDE"
                elif require_approved:
                    raise ValueError(
                        f"Cannot generate authoritative journal: Line item {idx + 1} has not been approved by Finance. "
                        f"approved_account_id and approved_account_name are required."
                    )
                elif ai_acc_id and ai_acc_name:
                    account_id = ai_acc_id
                    account_name = f"[Unapproved] {ai_acc_name}"
                    provenance = acc_info.get("provenance") or "AI_PREDICTED"
                elif ai_acc_id:
                    account_id = ai_acc_id
                    account_name = f"[Unapproved] {ai_acc_id}"
                    provenance = "AI_PREDICTED"
                else:
                    account_id = None
                    account_name = f"[Unapproved] Line {idx + 1} Expense"
                    provenance = "UNRESOLVED"
                    requires_review = True
                    errors.append(f"Missing COA account classification for line {idx + 1} ('{desc}').")

                line_type = "ASSET" if "asset" in account_name.lower() or account_id == "ACC_6" else "EXPENSE"

                lines.append(
                    JournalLine(
                        account_id=account_id,
                        account_name=account_name,
                        line_type=line_type,
                        debit=taxable,
                        credit=0.0,
                        amount=taxable,
                        source_line_index=idx + 1,
                        provenance=provenance,
                        description=desc,
                        cost_center=cost_center,
                        project=project,
                        department=department,
                    )
                )
                total_line_taxable_debits += taxable
        elif subtotal is not None and subtotal > 0:
            acc_info = accounting_list[0] if accounting_list else {}
            approved_acc_id = acc_info.get("approved_account_id") or acc_info.get("final_account_id")
            approved_acc_name = acc_info.get("approved_account_name") or acc_info.get("final_account_name")
            ai_acc_id = acc_info.get("ai_account_id") or acc_info.get("account_id")
            ai_acc_name = acc_info.get("ai_account_name") or acc_info.get("account_name") or (f"[Unapproved] {ai_acc_id}" if ai_acc_id else "[Unassigned Expense]")

            if approved_acc_id and approved_acc_name:
                acc_id = approved_acc_id
                acc_name = approved_acc_name
                prov = "HITL_OVERRIDE"
            elif require_approved:
                raise ValueError("Invoice lacks Finance-approved Chart of Accounts.")
            else:
                acc_id = ai_acc_id
                acc_name = ai_acc_name
                prov = "AI_PREDICTED" if accounting_list else "DETERMINISTIC"

            lines.append(
                JournalLine(
                    account_id=acc_id,
                    account_name=acc_name,
                    line_type="EXPENSE",
                    debit=subtotal,
                    credit=0.0,
                    amount=subtotal,
                    source_line_index=1,
                    provenance=prov,
                    description="Invoice Taxable Amount",
                    cost_center=cost_center,
                    project=project,
                    department=department,
                )
            )
            total_line_taxable_debits = subtotal

        # ----------------------------------------------------
        # 4. INPUT TAX (GST & ITC ENGINE) DEBITS
        # ----------------------------------------------------
        cgst_amt = 0.0
        sgst_amt = 0.0
        igst_amt = 0.0
        cess_amt = 0.0
        supply_type = "INTRA_STATE"

        effective_gst = gst_result
        if not effective_gst:
            from app.services.gst_engine import gst_engine
            effective_gst = gst_engine.evaluate_gst(inv)

        if effective_gst:
            supply_type = effective_gst.get("supply_type") or "INTRA_STATE"
            gst_calc = effective_gst.get("calculated") or {}
            gst_ext = effective_gst.get("extracted") or {}
            
            # Authoritatively consume calculated tax if valid, or extracted tax matching supply type
            if supply_type == "INTER_STATE":
                igst_amt = self._clean_num(gst_calc.get("igst_amount"))
                if igst_amt is None or igst_amt == 0.0:
                    igst_amt = self._clean_num(gst_ext.get("igst_amount")) or self._clean_num(inv.get("igst_amount") or inv.get("igst")) or 0.0
                cgst_amt = 0.0
                sgst_amt = 0.0
            elif supply_type == "INTRA_STATE":
                cgst_amt = self._clean_num(gst_calc.get("cgst_amount"))
                if cgst_amt is None or cgst_amt == 0.0:
                    cgst_amt = self._clean_num(gst_ext.get("cgst_amount")) or self._clean_num(inv.get("cgst_amount") or inv.get("cgst")) or 0.0
                sgst_amt = self._clean_num(gst_calc.get("sgst_amount"))
                if sgst_amt is None or sgst_amt == 0.0:
                    sgst_amt = self._clean_num(gst_ext.get("sgst_amount")) or self._clean_num(inv.get("sgst_amount") or inv.get("sgst")) or 0.0
                igst_amt = 0.0
            else:
                # REVIEW_REQUIRED
                cgst_amt = self._clean_num(gst_ext.get("cgst_amount")) or self._clean_num(inv.get("cgst_amount") or inv.get("cgst")) or 0.0
                sgst_amt = self._clean_num(gst_ext.get("sgst_amount")) or self._clean_num(inv.get("sgst_amount") or inv.get("sgst")) or 0.0
                igst_amt = self._clean_num(gst_ext.get("igst_amount")) or self._clean_num(inv.get("igst_amount") or inv.get("igst")) or 0.0

            cess_amt = self._clean_num(gst_calc.get("cess_amount") or gst_ext.get("cess_amount") or inv.get("cess_amount") or inv.get("cess")) or 0.0
        else:
            cgst_amt = self._clean_num(inv.get("cgst_amount") or inv.get("cgst")) or 0.0
            sgst_amt = self._clean_num(inv.get("sgst_amount") or inv.get("sgst")) or 0.0
            igst_amt = self._clean_num(inv.get("igst_amount") or inv.get("igst")) or 0.0
            cess_amt = self._clean_num(inv.get("cess_amount") or inv.get("cess")) or 0.0

        total_extracted_gst = round(cgst_amt + sgst_amt + igst_amt + cess_amt, 2)
        unitemized_tax_amt = 0.0

        # Unitemized tax: If header has tax_total > 0 and no explicit CGST/SGST/IGST breakdown exists at all,
        # DO NOT synthesize a fake 50/50 split. Flag transaction for review and book to pending review tax expense
        # so that journal remains mathematically grounded to actual invoice total obligation without balancing hacks.
        if total_extracted_gst == 0.0 and tax_total is not None and tax_total > 0:
            requires_review = True
            unitemized_tax_amt = round(tax_total, 2)
            warnings.append(
                f"Invoice contains unitemized Tax Total (₹{tax_total:,.2f}) without explicit CGST/SGST/IGST breakdown. "
                "Review required; synthetic tax split is prohibited."
            )
            lines.append(
                JournalLine(
                    account_id=STANDARD_ACCOUNTS["INELIGIBLE_TAX"]["account_id"],
                    account_name="Unitemized Tax (Pending Review)",
                    line_type="EXPENSE",
                    debit=unitemized_tax_amt,
                    credit=0.0,
                    amount=unitemized_tax_amt,
                    provenance="DETERMINISTIC",
                    description=f"Unitemized Tax Total ₹{unitemized_tax_amt:,.2f} awaiting manual tax-type classification",
                    cost_center=cost_center,
                    project=project,
                    department=department,
                    rule_reference="Review Required - No Fake 50/50 Split",
                )
            )

        # Authoritative ITC Evaluation Consumption
        itc_status = "ELIGIBLE"
        eligible_tax = total_extracted_gst
        blocked_tax = 0.0
        reversal_tax = 0.0
        review_tax = 0.0

        if itc_result:
            itc_status = itc_result.get("status") or "ELIGIBLE"
            eligible_tax = self._clean_num(itc_result.get("eligible_itc") if itc_result.get("eligible_itc") is not None else itc_result.get("eligible_amount"))
            if eligible_tax is None:
                eligible_tax = total_extracted_gst if itc_status == "ELIGIBLE" else 0.0
            blocked_tax = self._clean_num(itc_result.get("blocked_itc") if itc_result.get("blocked_itc") is not None else itc_result.get("ineligible_amount")) or 0.0
            reversal_tax = self._clean_num(itc_result.get("reversal_itc")) or 0.0
            review_tax = self._clean_num(itc_result.get("review_amount")) or 0.0

        if itc_status == "INELIGIBLE":
            if total_extracted_gst > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["INELIGIBLE_TAX"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["INELIGIBLE_TAX"]["account_name"],
                        line_type="EXPENSE",
                        debit=total_extracted_gst,
                        credit=0.0,
                        amount=total_extracted_gst,
                        provenance="DETERMINISTIC",
                        description=f"Ineligible/Blocked Input Tax under Sec 17(5) ({itc_result.get('rule_reference') if itc_result else 'Sec 17(5)'})",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                        rule_reference=itc_result.get("rule_reference") if itc_result else "CGST Act Sec 17(5)",
                    )
                )
        elif itc_status == "ELIGIBLE":
            if cgst_amt > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["INPUT_CGST"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["INPUT_CGST"]["account_name"],
                        line_type="INPUT_TAX",
                        debit=cgst_amt,
                        credit=0.0,
                        amount=cgst_amt,
                        provenance="DETERMINISTIC",
                        description="Input CGST (Eligible)",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                        rule_reference="CGST Act Sec 16(1)",
                    )
                )
            if sgst_amt > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["INPUT_SGST"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["INPUT_SGST"]["account_name"],
                        line_type="INPUT_TAX",
                        debit=sgst_amt,
                        credit=0.0,
                        amount=sgst_amt,
                        provenance="DETERMINISTIC",
                        description="Input SGST / UTGST (Eligible)",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                        rule_reference="CGST Act Sec 16(1)",
                    )
                )
            if igst_amt > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["INPUT_IGST"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["INPUT_IGST"]["account_name"],
                        line_type="INPUT_TAX",
                        debit=igst_amt,
                        credit=0.0,
                        amount=igst_amt,
                        provenance="DETERMINISTIC",
                        description="Input IGST (Eligible)",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                        rule_reference="CGST Act Sec 16(1)",
                    )
                )
            if cess_amt > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["INPUT_CESS"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["INPUT_CESS"]["account_name"],
                        line_type="INPUT_TAX",
                        debit=cess_amt,
                        credit=0.0,
                        amount=cess_amt,
                        provenance="DETERMINISTIC",
                        description="Input Cess (Eligible)",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                    )
                )
        else:
            # PARTIALLY_ELIGIBLE or REVIEW_REQUIRED
            requires_review = True
            warnings.append(f"ITC status is {itc_status}. Input tax requires verification.")
            
            # 1. Eligible Portion -> Input GST Asset
            if eligible_tax > 0:
                ratio = eligible_tax / (total_extracted_gst if total_extracted_gst > 0 else 1.0)
                if cgst_amt > 0:
                    lines.append(
                        JournalLine(
                            account_id=STANDARD_ACCOUNTS["INPUT_CGST"]["account_id"],
                            account_name=STANDARD_ACCOUNTS["INPUT_CGST"]["account_name"],
                            line_type="INPUT_TAX",
                            debit=round(cgst_amt * ratio, 2),
                            credit=0.0,
                            amount=round(cgst_amt * ratio, 2),
                            provenance="DETERMINISTIC",
                            description="Input CGST (Eligible Portion)",
                            cost_center=cost_center,
                            project=project,
                            department=department,
                            rule_reference=itc_result.get("rule_reference") if itc_result else "CGST Act Sec 16",
                        )
                    )
                if sgst_amt > 0:
                    lines.append(
                        JournalLine(
                            account_id=STANDARD_ACCOUNTS["INPUT_SGST"]["account_id"],
                            account_name=STANDARD_ACCOUNTS["INPUT_SGST"]["account_name"],
                            line_type="INPUT_TAX",
                            debit=round(sgst_amt * ratio, 2),
                            credit=0.0,
                            amount=round(sgst_amt * ratio, 2),
                            provenance="DETERMINISTIC",
                            description="Input SGST (Eligible Portion)",
                            cost_center=cost_center,
                            project=project,
                            department=department,
                            rule_reference=itc_result.get("rule_reference") if itc_result else "CGST Act Sec 16",
                        )
                    )
                if igst_amt > 0:
                    lines.append(
                        JournalLine(
                            account_id=STANDARD_ACCOUNTS["INPUT_IGST"]["account_id"],
                            account_name=STANDARD_ACCOUNTS["INPUT_IGST"]["account_name"],
                            line_type="INPUT_TAX",
                            debit=round(igst_amt * ratio, 2),
                            credit=0.0,
                            amount=round(igst_amt * ratio, 2),
                            provenance="DETERMINISTIC",
                            description="Input IGST (Eligible Portion)",
                            cost_center=cost_center,
                            project=project,
                            department=department,
                            rule_reference=itc_result.get("rule_reference") if itc_result else "CGST Act Sec 16",
                        )
                    )

            # 2. Blocked Portion -> Ineligible Tax Expense
            if blocked_tax > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["INELIGIBLE_TAX"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["INELIGIBLE_TAX"]["account_name"],
                        line_type="EXPENSE",
                        debit=blocked_tax,
                        credit=0.0,
                        amount=blocked_tax,
                        provenance="DETERMINISTIC",
                        description="Ineligible Input Tax Expense under Section 17(5)",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                        rule_reference=itc_result.get("rule_reference") if itc_result else "CGST Act Sec 17(5)",
                    )
                )

            # 3. Review Required or Reversal Portion -> Preserved in Ineligible Tax Expense pending review
            pending_review_amt = round(review_tax + reversal_tax, 2)
            if pending_review_amt > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["INELIGIBLE_TAX"]["account_id"],
                        account_name="Input Tax Pending Verification",
                        line_type="EXPENSE",
                        debit=pending_review_amt,
                        credit=0.0,
                        amount=pending_review_amt,
                        provenance="DETERMINISTIC",
                        description="Input Tax flagged for review / Rule 37/42 reversal (Not claimable as asset)",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                        rule_reference=itc_result.get("rule_reference") if itc_result else "CGST Act Sec 16",
                    )
                )

        # ----------------------------------------------------
        # 5. SECONDARY CHARGES & ROUND-OFF DEBITS / CREDITS
        # ----------------------------------------------------
        if shipping > 0:
            lines.append(
                JournalLine(
                    account_id=STANDARD_ACCOUNTS["SHIPPING_CHARGES"]["account_id"],
                    account_name=STANDARD_ACCOUNTS["SHIPPING_CHARGES"]["account_name"],
                    line_type="EXPENSE",
                    debit=shipping,
                    credit=0.0,
                    amount=shipping,
                    provenance="DETERMINISTIC",
                    description="Shipping & Freight Charges",
                    cost_center=cost_center,
                    project=project,
                    department=department,
                )
            )

        if other_charges > 0:
            lines.append(
                JournalLine(
                    account_id=STANDARD_ACCOUNTS["OTHER_CHARGES"]["account_id"],
                    account_name=STANDARD_ACCOUNTS["OTHER_CHARGES"]["account_name"],
                    line_type="EXPENSE",
                    debit=other_charges,
                    credit=0.0,
                    amount=other_charges,
                    provenance="DETERMINISTIC",
                    description="Other Direct Expenses / Handling",
                    cost_center=cost_center,
                    project=project,
                    department=department,
                )
            )

        if round_off != 0.0:
            if round_off > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["ROUND_OFF"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["ROUND_OFF"]["account_name"],
                        line_type="ROUND_OFF",
                        debit=round_off,
                        credit=0.0,
                        amount=round_off,
                        provenance="DETERMINISTIC",
                        description="Round Off Adjustment (+)",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                    )
                )
            else:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["ROUND_OFF"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["ROUND_OFF"]["account_name"],
                        line_type="ROUND_OFF",
                        debit=0.0,
                        credit=abs(round_off),
                        amount=abs(round_off),
                        provenance="DETERMINISTIC",
                        description="Round Off Adjustment (-)",
                        cost_center=cost_center,
                        project=project,
                        department=department,
                    )
                )

        # ----------------------------------------------------
        # 6. TDS TREATMENT (WITHHOLDING TAX CREDIT)
        # ----------------------------------------------------
        from app.services.tds_engine import get_effective_tds_data, tds_engine

        if isinstance(tds_result, dict) and bool(tds_result):
            raw_app = tds_result.get("tds_applicable") if "tds_applicable" in tds_result else tds_result.get("applicable")
            tds_applicable = bool(raw_app) if raw_app is not None else False
            tds_data = tds_result
        else:
            tds_data = get_effective_tds_data(accounting_classification)
            tds_applicable = bool(tds_data.get("applicable"))

        tds_provision = tds_data.get("approved_tds_provision") or tds_data.get("tds_provision") or tds_data.get("provision")
        tds_section = tds_data.get("approved_tds_section") or tds_data.get("tds_section") or tds_data.get("section")
        tds_nature = tds_data.get("approved_nature_of_payment") or tds_data.get("nature_of_payment") or tds_data.get("nature")
        tds_rate = self._clean_num(
            tds_data.get("approved_tds_rate")
            or tds_data.get("tds_rate")
            or tds_data.get("rate")
        )
        tds_amount = self._clean_num(
            tds_data.get("final_tds_amount")
            or tds_data.get("calculated_tds_amount")
            or tds_data.get("tds_amount")
            or tds_data.get("amount")
        ) or 0.0
        is_approved = tds_data.get("is_approved")
        if is_approved is None:
            is_approved = tds_data.get("approved")

        if not tds_applicable:
            tds_amount = 0.0
            tds_rate = 0.0
        elif subtotal is not None and subtotal > 0:
            if tds_rate is not None and tds_rate > 0:
                tds_amount = round((subtotal * float(tds_rate)) / 100.0, 2)
            elif tds_amount <= 0:
                calc = tds_engine.calculate_tds(
                    applicable=True,
                    section=tds_section,
                    provision=tds_provision,
                    nature_of_payment=tds_nature,
                    base_amount=subtotal,
                    rate=tds_rate,
                )
                tds_amount = calc.get("tds_amount", 0.0)
                tds_rate = calc.get("rate", tds_rate)

        if tds_applicable and tds_amount > 0:
            if is_approved is not True:
                requires_review = True
                warnings.append("Proposed TDS requires finance approval.")

            label = f"{tds_provision or ''} {tds_section or ''}".strip() or (tds_nature or "TDS")
            lines.append(
                JournalLine(
                    account_id=STANDARD_ACCOUNTS["TDS_PAYABLE"]["account_id"],
                    account_name=STANDARD_ACCOUNTS["TDS_PAYABLE"]["account_name"],
                    line_type="TDS_PAYABLE",
                    debit=0.0,
                    credit=tds_amount,
                    amount=tds_amount,
                    provenance="HITL_OVERRIDE" if is_approved else "AI_PREDICTED",
                    description=f"TDS Withholding - {label} ({tds_rate or ''}%)",
                    cost_center=cost_center,
                    project=project,
                    department=department,
                )
            )
        elif tds_applicable and tds_amount == 0.0:
            requires_review = True
            warnings.append("TDS is marked applicable but withholding amount is unresolved.")

        # ----------------------------------------------------
        # 7. ACCOUNTS PAYABLE / VENDOR LIABILITY CREDIT
        # ----------------------------------------------------
        gross_invoice_obligation = total_amount
        if gross_invoice_obligation is None:
            gross_invoice_obligation = (
                total_line_taxable_debits
                + total_extracted_gst
                + shipping
                + other_charges
                + round_off
            )

        vendor_payable = round(gross_invoice_obligation - tds_amount, 2)
        if vendor_payable < 0:
            vendor_payable = 0.0
            errors.append("Vendor payable calculated to negative amount due to excessive TDS.")
            requires_review = True

        lines.append(
            JournalLine(
                account_id=STANDARD_ACCOUNTS["ACCOUNTS_PAYABLE"]["account_id"],
                account_name=f"Accounts Payable - {vendor_name}",
                line_type="ACCOUNTS_PAYABLE",
                debit=0.0,
                credit=vendor_payable,
                amount=vendor_payable,
                provenance="DETERMINISTIC",
                description=f"Payable to {vendor_name}",
                cost_center=cost_center,
                project=project,
                department=department,
            )
        )

        # ----------------------------------------------------
        # 8. JOURNAL BALANCING & STATUS EVALUATION
        # ----------------------------------------------------
        total_debit = round(sum(l.debit for l in lines), 2)
        total_credit = round(sum(l.credit for l in lines), 2)
        difference = round(total_debit - total_credit, 2)

        is_balanced = abs(difference) <= self.tolerance

        if not is_balanced:
            errors.append(
                f"Journal unbalanced: Total Debits (₹{total_debit:,.2f}) != Total Credits (₹{total_credit:,.2f}) (diff: ₹{difference:,.2f})."
            )
            overall_status = "UNBALANCED"
        elif requires_review or errors:
            overall_status = "REVIEW_REQUIRED"
        else:
            overall_status = "BALANCED"

        result = JournalEntryResult(
            status=overall_status,
            total_debit=total_debit,
            total_credit=total_credit,
            difference=difference,
            currency="INR",
            lines=lines,
            validation=JournalValidation(
                balanced=is_balanced,
                tolerance=self.tolerance,
                errors=errors,
                warnings=warnings,
            ),
        )

        return result.model_dump()

    def generate_journal_entry(
        self,
        invoice_data: Dict[str, Any],
        accounting_data: Optional[Dict[str, Any]] = None,
        gst_result: Optional[Dict[str, Any]] = None,
        itc_result: Optional[Dict[str, Any]] = None,
        tds_result: Optional[Dict[str, Any]] = None,
        financial_validation_result: Optional[Dict[str, Any]] = None,
        cost_center: Optional[str] = None,
        project: Optional[str] = None,
        department: Optional[str] = None,
        require_approved: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Unified compatibility wrapper delegating to the single authoritative generate_journal engine.
        Returns legacy dictionary format while ensuring 100% accounting and balance identity.
        """
        res = self.generate_journal(
            invoice_data=invoice_data,
            accounting_classification=accounting_data,
            gst_result=gst_result,
            itc_result=itc_result,
            tds_result=tds_result,
            financial_validation_result=financial_validation_result,
            cost_center=cost_center,
            project=project,
            department=department,
            require_approved=require_approved,
        )

        inv = invoice_data.get("data", invoice_data) if isinstance(invoice_data, dict) else {}
        inv_date = inv.get("invoice_date")
        supply_type = (gst_result or {}).get("supply_type") or "INTRA_STATE"

        legacy_lines = []
        for idx, line in enumerate(res.get("lines", []), 1):
            line_type = "DR" if line.get("debit", 0.0) > 0 else "CR"
            amt = line.get("debit", 0.0) if line_type == "DR" else line.get("credit", 0.0)
            
            raw_acc_id = line.get("account_id")
            # Provide AP_VENDOR alias if this is Accounts Payable for backward compatibility
            acc_id_alias = raw_acc_id
            if raw_acc_id == "LIAB_AP":
                acc_id_alias = "AP_VENDOR"
            elif raw_acc_id == "TAX_INP_CGST":
                acc_id_alias = "INPUT_CGST"
            elif raw_acc_id == "TAX_INP_SGST":
                acc_id_alias = "INPUT_SGST"
            elif raw_acc_id == "TAX_INP_IGST":
                acc_id_alias = "INPUT_IGST"

            legacy_lines.append({
                "line_number": idx,
                "account_id": acc_id_alias,
                "account_name": line.get("account_name"),
                "is_approved": line.get("provenance") == "HITL_OVERRIDE" or ("[Unapproved]" not in line.get("account_name", "")),
                "line_type": line_type,
                "amount": amt,
                "debit": line.get("debit", 0.0),
                "credit": line.get("credit", 0.0),
                "description": line.get("description"),
                "cost_center": line.get("cost_center"),
            })

        return {
            "entry_date": inv_date,
            "supply_type": supply_type,
            "total_debit": res.get("total_debit", 0.0),
            "total_credit": res.get("total_credit", 0.0),
            "is_balanced": res.get("validation", {}).get("balanced", False),
            "status": res.get("status"),
            "has_unapproved_lines": any(not l.get("is_approved") for l in legacy_lines),
            "difference": res.get("difference", 0.0),
            "lines": legacy_lines,
            "validation": res.get("validation", {}),
        }

    def _clean_num(self, val: Any) -> Optional[float]:
        """Helper to parse clean float numeric values from string, float, int or None."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = re.sub(r"[^\d.-]", "", val)
            if not cleaned or cleaned in ("-", "."):
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None


# Singleton instance for application use
journal_generator = JournalGenerator()


async def sync_relational_journal(session, invoice_id, journal_dict: Dict[str, Any], tenant_id: str = "default-tenant-001"):
    """
    Idempotently syncs relational journal_entries and journal_lines tables
    from the authoritative journal generator result.
    """
    if not journal_dict or not isinstance(journal_dict, dict):
        return None

    try:
        from sqlalchemy import select, delete
        from app.db.models import JournalEntry, JournalLineModel
        import uuid

        # Check existing journal entry
        query = select(JournalEntry).where(JournalEntry.invoice_id == invoice_id)
        res = await session.execute(query)
        entry = res.scalar_one_or_none()

        is_bal = bool(journal_dict.get("validation", {}).get("balanced") or journal_dict.get("is_balanced", False))
        tot_dr = float(journal_dict.get("total_debit", 0.0))
        tot_cr = float(journal_dict.get("total_credit", 0.0))
        diff = float(journal_dict.get("difference", 0.0))
        status_val = journal_dict.get("status", "BALANCED" if is_bal else "UNBALANCED")

        if entry:
            entry.status = status_val
            entry.total_debit = tot_dr
            entry.total_credit = tot_cr
            entry.difference = diff
            entry.balanced = is_bal
            entry.is_balanced = is_bal
            
            # Delete old lines to prevent duplication
            await session.execute(
                delete(JournalLineModel).where(JournalLineModel.journal_entry_id == entry.id)
            )
        else:
            entry = JournalEntry(
                id=uuid.uuid4(),
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                status=status_val,
                total_debit=tot_dr,
                total_credit=tot_cr,
                difference=diff,
                balanced=is_bal,
                is_balanced=is_bal,
            )
            session.add(entry)
            await session.flush()

        # Insert new lines
        raw_lines = journal_dict.get("lines") or []
        for idx, line in enumerate(raw_lines):
            debit_val = float(line.get("debit", 0.0))
            credit_val = float(line.get("credit", 0.0))
            amount_val = float(line.get("amount", debit_val or credit_val or 0.0))
            line_type = line.get("line_type", "EXPENSE")
            
            jl = JournalLineModel(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                line_number=idx + 1,
                account_id=line.get("account_id", "ACC_UNKNOWN"),
                account_name=line.get("account_name", "Unknown Account"),
                line_type=line_type,
                debit=debit_val,
                credit=credit_val,
                amount=amount_val,
                source_line_index=line.get("source_line_index"),
                provenance=line.get("provenance", "DETERMINISTIC"),
                description=line.get("description"),
                cost_center=line.get("cost_center"),
                project=line.get("project"),
                department=line.get("department"),
            )
            session.add(jl)

        return entry
    except Exception as exc:
        logger.warning(f"Failed to sync relational journal entry for invoice {invoice_id}: {exc}")
        return None
