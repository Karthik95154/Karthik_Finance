import logging
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

DEFAULT_TOLERANCE = 1.0  # 1 INR tolerance for rounding


class JournalLine(BaseModel):
    account_id: str
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
    Deterministic Double-Entry Accounting Journal Generator for Invoices.
    Generates preview accounting journal entries from effective extraction,
    COA classification, GST, ITC, TDS, and Financial Validation results.
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
    ) -> Dict[str, Any]:
        """
        Main entrypoint to generate a double-entry journal preview.
        """
        lines: List[JournalLine] = []
        errors: List[str] = []
        warnings: List[str] = []
        requires_review: bool = False

        # Extract underlying invoice payload if wrapped
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
                warnings.append(
                    "Stage 5 Financial Validation requires review."
                )

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
        tax_total = self._clean_num(inv.get("tax_total"))
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

                acc_info = acc_by_index.get(idx) or (accounting_list[idx] if idx < len(accounting_list) else {})
                final_acc_id = acc_info.get("final_account_id")
                final_acc_name = acc_info.get("final_account_name")
                ai_acc_id = acc_info.get("ai_account_id") or acc_info.get("account_id")
                ai_acc_name = acc_info.get("ai_account_name") or acc_info.get("account_name")

                if final_acc_id and final_acc_name:
                    account_id = final_acc_id
                    account_name = final_acc_name
                    provenance = "HITL_OVERRIDE"
                elif ai_acc_id and ai_acc_name:
                    account_id = ai_acc_id
                    account_name = ai_acc_name
                    provenance = acc_info.get("provenance") or "AI_PREDICTED"
                elif ai_acc_id:
                    account_id = ai_acc_id
                    account_name = ai_acc_name or ai_acc_id
                    provenance = "AI_PREDICTED"
                else:
                    account_id = f"UNCLASSIFIED_EXPENSE_{idx + 1}"
                    account_name = f"Unclassified Expense ({desc})"
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
                        source_line_index=idx,
                        provenance=provenance,
                        description=desc,
                    )
                )
                total_line_taxable_debits += taxable
        elif subtotal is not None and subtotal > 0:
            acc_info = accounting_list[0] if accounting_list else {}
            final_acc_id = acc_info.get("final_account_id")
            final_acc_name = acc_info.get("final_acc_name") or acc_info.get("final_account_name")
            ai_acc_id = acc_info.get("ai_account_id") or acc_info.get("account_id") or "ACC_3"
            ai_acc_name = acc_info.get("ai_account_name") or acc_info.get("account_name") or "Office Supplies & Stationery"

            if final_acc_id and final_acc_name:
                acc_id = final_acc_id
                acc_name = final_acc_name
                prov = "HITL_OVERRIDE"
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
                    source_line_index=0,
                    provenance=prov,
                    description="Invoice Taxable Amount",
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

        if gst_result:
            supply_type = gst_result.get("supply_type") or "INTRA_STATE"
            gst_calc = gst_result.get("calculated") or {}
            gst_ext = gst_result.get("extracted") or {}
            
            cgst_amt = self._clean_num(gst_calc.get("cgst_amount") or gst_ext.get("cgst_amount")) or 0.0
            sgst_amt = self._clean_num(gst_calc.get("sgst_amount") or gst_ext.get("sgst_amount")) or 0.0
            igst_amt = self._clean_num(gst_calc.get("igst_amount") or gst_ext.get("igst_amount")) or 0.0
            cess_amt = self._clean_num(gst_calc.get("cess_amount") or gst_ext.get("cess_amount")) or 0.0
        else:
            cgst_amt = self._clean_num(inv.get("cgst_amount") or inv.get("cgst")) or 0.0
            sgst_amt = self._clean_num(inv.get("sgst_amount") or inv.get("sgst")) or 0.0
            igst_amt = self._clean_num(inv.get("igst_amount") or inv.get("igst")) or 0.0
            cess_amt = self._clean_num(inv.get("cess_amount") or inv.get("cess")) or 0.0

        total_extracted_gst = cgst_amt + sgst_amt + igst_amt + cess_amt
        if total_extracted_gst == 0.0 and tax_total is not None and tax_total > 0:
            if supply_type == "INTER_STATE":
                igst_amt = tax_total
            else:
                cgst_amt = round(tax_total / 2.0, 2)
                sgst_amt = round(tax_total - cgst_amt, 2)

        itc_status = "ELIGIBLE"
        eligible_tax = total_extracted_gst
        ineligible_tax = 0.0

        if itc_result:
            itc_status = itc_result.get("status") or "ELIGIBLE"
            eligible_tax = self._clean_num(itc_result.get("eligible_amount"))
            if eligible_tax is None:
                eligible_tax = total_extracted_gst if itc_status == "ELIGIBLE" else 0.0
            ineligible_tax = self._clean_num(itc_result.get("ineligible_amount")) or 0.0

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
                    )
                )
        else:
            requires_review = True
            warnings.append(f"ITC status is {itc_status}. Input tax eligibility requires verification.")
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
                        )
                    )
            if ineligible_tax > 0:
                lines.append(
                    JournalLine(
                        account_id=STANDARD_ACCOUNTS["INELIGIBLE_TAX"]["account_id"],
                        account_name=STANDARD_ACCOUNTS["INELIGIBLE_TAX"]["account_name"],
                        line_type="EXPENSE",
                        debit=ineligible_tax,
                        credit=0.0,
                        amount=ineligible_tax,
                        provenance="DETERMINISTIC",
                        description="Ineligible Input Tax Expense",
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
                    )
                )

        # ----------------------------------------------------
        # 6. TDS TREATMENT (WITHHOLDING TAX CREDIT)
        # ----------------------------------------------------
        tds_data = tds_result or (accounting_classification.get("tds") if accounting_classification else {}) or {}
        tds_applicable = tds_data.get("tds_applicable") or tds_data.get("is_applicable")
        tds_amount = self._clean_num(
            tds_data.get("final_tds_amount")
            or tds_data.get("tds_amount")
            or tds_data.get("amount")
        ) or 0.0
        tds_section = tds_data.get("tds_section") or tds_data.get("section") or "194C/194J"
        is_approved = tds_data.get("is_approved")
        if is_approved is None:
            is_approved = tds_data.get("approved")

        if tds_applicable and tds_amount > 0:
            if is_approved is not True:
                requires_review = True
                warnings.append("Proposed TDS requires finance approval.")

            lines.append(
                JournalLine(
                    account_id=STANDARD_ACCOUNTS["TDS_PAYABLE"]["account_id"],
                    account_name=STANDARD_ACCOUNTS["TDS_PAYABLE"]["account_name"],
                    line_type="TDS_PAYABLE",
                    debit=0.0,
                    credit=tds_amount,
                    amount=tds_amount,
                    provenance="HITL_OVERRIDE" if is_approved else "AI_PREDICTED",
                    description=f"TDS Withholding under Section {tds_section}",
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
                account_name=STANDARD_ACCOUNTS["ACCOUNTS_PAYABLE"]["account_name"],
                line_type="ACCOUNTS_PAYABLE",
                debit=0.0,
                credit=vendor_payable,
                amount=vendor_payable,
                provenance="DETERMINISTIC",
                description=f"Payable to {vendor_name}",
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

    # Compatibility alias for main branch calls
    generate_journal_entry = generate_journal

    def _clean_num(self, val: Any) -> Optional[float]:
        """Helper to parse clean float numeric values from string, float, int or None."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            import re
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


async def sync_relational_journal(session, invoice_id, journal_dict: Dict[str, Any]):
    """
    Idempotently syncs or updates relational journal_entries and journal_lines
    tables from the generated journal preview dictionary.
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

        if entry:
            entry.status = journal_dict.get("status", "BALANCED")
            entry.total_debit = float(journal_dict.get("total_debit", 0.0))
            entry.total_credit = float(journal_dict.get("total_credit", 0.0))
            entry.difference = float(journal_dict.get("difference", 0.0))
            entry.balanced = bool(journal_dict.get("validation", {}).get("balanced", True))
            entry.is_balanced = entry.balanced
            
            # Delete old lines to prevent duplication
            await session.execute(
                delete(JournalLineModel).where(JournalLineModel.journal_entry_id == entry.id)
            )
        else:
            entry = JournalEntry(
                id=uuid.uuid4(),
                invoice_id=invoice_id,
                status=journal_dict.get("status", "BALANCED"),
                total_debit=float(journal_dict.get("total_debit", 0.0)),
                total_credit=float(journal_dict.get("total_credit", 0.0)),
                difference=float(journal_dict.get("difference", 0.0)),
                balanced=bool(journal_dict.get("validation", {}).get("balanced", True)),
                is_balanced=bool(journal_dict.get("validation", {}).get("balanced", True)),
            )
            session.add(entry)
            await session.flush()

        # Insert new lines
        raw_lines = journal_dict.get("lines") or []
        for idx, line in enumerate(raw_lines):
            debit_val = float(line.get("debit", 0.0))
            credit_val = float(line.get("credit", 0.0))
            amount_val = float(line.get("amount", debit_val or credit_val or 0.0))
            
            jl = JournalLineModel(
                id=uuid.uuid4(),
                journal_entry_id=entry.id,
                line_number=idx + 1,
                account_id=line.get("account_id", "ACC_UNKNOWN"),
                account_name=line.get("account_name", "Unknown Account"),
                line_type=line.get("line_type", "EXPENSE"),
                debit=debit_val,
                credit=credit_val,
                amount=amount_val,
                source_line_index=line.get("source_line_index"),
                provenance=line.get("provenance", "DETERMINISTIC"),
                description=line.get("description"),
            )
            session.add(jl)

        return entry
    except Exception as exc:
        logger.warning(f"Failed to sync relational journal entry for invoice {invoice_id}: {exc}")
        return None
