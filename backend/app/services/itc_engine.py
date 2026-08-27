import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ITCEngine:
    """
    Deterministic Input Tax Credit (ITC) Engine implementing statutory eligibility
    rules under Section 16 and blocked credit provisions under Section 17(5) of the CGST Act.
    """

    def evaluate_line_itc(
        self,
        description: str,
        account_name: Optional[str],
        account_id: Optional[str],
        hsn_code: Optional[str],
        tax_amount: float,
        is_reverse_charge: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluates a single line item against Section 17(5) blocked credit rules
        and Section 16 business eligibility criteria.
        """
        desc_lower = description.lower()
        acc_lower = (account_name or "").lower()

        # Rule 1: Section 17(5)(b)(i) - Food & Beverages, Catering, Personal Grooming & Healthcare
        food_patterns = [
            r"\b(food|beverage|catering|restaurant|meal|snacks|refreshments|lunch|dinner|breakfast|canteen|tea|coffee)\b",
            r"\b(beauty treatment|cosmetic|plastic surgery|spa|salon|health services)\b",
        ]
        if any(re.search(p, desc_lower) for p in food_patterns) or any(re.search(p, acc_lower) for p in food_patterns):
            return {
                "itc_status": "INELIGIBLE",
                "eligible_amount": 0.0,
                "ineligible_amount": tax_amount,
                "reason": "Food, beverages, outdoor catering, and personal grooming are blocked under CGST Act Section 17(5)(b)(i).",
                "rule_reference": "CGST Act Sec 17(5)(b)(i)",
            }

        # Rule 2: Section 17(5)(b)(ii) - Club Membership & Fitness
        club_patterns = [
            r"\b(club membership|gym|gymnasium|fitness center|fitness centre|health club|recreational club)\b"
        ]
        if any(re.search(p, desc_lower) for p in club_patterns) or any(re.search(p, acc_lower) for p in club_patterns):
            return {
                "itc_status": "INELIGIBLE",
                "eligible_amount": 0.0,
                "ineligible_amount": tax_amount,
                "reason": "Membership of a club, health, and fitness centre is blocked under CGST Act Section 17(5)(b)(ii).",
                "rule_reference": "CGST Act Sec 17(5)(b)(ii)",
            }

        # Rule 3: Section 17(5)(a) - Motor Vehicles for personal transport
        vehicle_patterns = [
            r"\b(motor vehicle|passenger car|sedan|suv|hatchback|two wheeler|motorcycle|scooter|personal vehicle)\b"
        ]
        if any(re.search(p, desc_lower) for p in vehicle_patterns):
            return {
                "itc_status": "INELIGIBLE",
                "eligible_amount": 0.0,
                "ineligible_amount": tax_amount,
                "reason": "Passenger motor vehicles with seating capacity <= 13 are blocked under CGST Act Section 17(5)(a) unless used for specified taxable supply.",
                "rule_reference": "CGST Act Sec 17(5)(a)",
            }

        # Rule 4: Section 17(5)(b)(iii) - Travel benefits to employees (LTA/vacation)
        vacation_patterns = [
            r"\b(leave travel|lta|employee vacation|holiday package|recreational tour)\b"
        ]
        if any(re.search(p, desc_lower) for p in vacation_patterns) or any(re.search(p, acc_lower) for p in vacation_patterns):
            return {
                "itc_status": "INELIGIBLE",
                "eligible_amount": 0.0,
                "ineligible_amount": tax_amount,
                "reason": "Travel benefits extended to employees on vacation are blocked under CGST Act Section 17(5)(b)(iii).",
                "rule_reference": "CGST Act Sec 17(5)(b)(iii)",
            }

        # Rule 5: Section 17(5)(c) & (d) - Works contract & construction of immovable property
        construction_patterns = [
            r"\b(works contract for construction of building|civil construction of office building|civil construction of immovable)\b"
        ]
        if any(re.search(p, desc_lower) for p in construction_patterns):
            return {
                "itc_status": "INELIGIBLE",
                "eligible_amount": 0.0,
                "ineligible_amount": tax_amount,
                "reason": "Works contract and goods/services for construction of immovable property capitalized to own account are blocked under CGST Act Sec 17(5)(c)/(d).",
                "rule_reference": "CGST Act Sec 17(5)(c)/(d)",
            }

        # Rule 6: Section 17(5)(h) - Goods lost, stolen, written off, gifts, free samples
        gift_patterns = [
            r"\b(gift|free sample|complimentary gift|corporate gift|giveaway)\b"
        ]
        if any(re.search(p, desc_lower) for p in gift_patterns):
            return {
                "itc_status": "INELIGIBLE",
                "eligible_amount": 0.0,
                "ineligible_amount": tax_amount,
                "reason": "Goods disposed of by way of gift or free samples are blocked under CGST Act Section 17(5)(h).",
                "rule_reference": "CGST Act Sec 17(5)(h)",
            }

        # Rule 7: Section 17(5)(g) - Personal consumption
        personal_patterns = [
            r"\b(personal consumption|personal use|personal expense|domestic use)\b"
        ]
        if any(re.search(p, desc_lower) for p in personal_patterns):
            return {
                "itc_status": "INELIGIBLE",
                "eligible_amount": 0.0,
                "ineligible_amount": tax_amount,
                "reason": "Goods or services used for personal consumption are blocked under CGST Act Section 17(5)(g).",
                "rule_reference": "CGST Act Sec 17(5)(g)",
            }

        # Rule 8: Section 16(1) - Proven Core Business Operations & Essential Inputs
        eligible_coa_patterns = [
            r"\b(cloud|hosting|infrastructure|software|saas|subscription|hardware|server|data center|machinery|plant and machinery|factory equipment|raw material|manufacturing|office supplies|stationery|consulting|professional|legal|audit|accounting fees|marketing|advertising|logistics|freight|courier|transport|telecom|internet|utilities|electricity|maintenance|repairs and maintenance)\b"
        ]
        if any(re.search(p, acc_lower) for p in eligible_coa_patterns) or any(re.search(p, desc_lower) for p in eligible_coa_patterns):
            rc_note = " (Eligible upon recipient discharging RCM liability in cash under Sec 16(2))" if is_reverse_charge else ""
            return {
                "itc_status": "ELIGIBLE",
                "eligible_amount": tax_amount,
                "ineligible_amount": 0.0,
                "reason": f"Core business input / service used in furtherance of business under CGST Act Section 16(1).{rc_note}",
                "rule_reference": "CGST Act Sec 16(1)",
            }

        # Rule 9: Ambiguous, retail, or unverified context -> REVIEW_REQUIRED
        ambiguous_patterns = [
            r"\b(assorted retail|consumer goods|packed goods|retail merchandise|store replenishment|dailykart|miscellaneous|general supplies|store items|sundry)\b"
        ]
        if any(re.search(p, desc_lower) for p in ambiguous_patterns) or not description or description == "Not provided":
            return {
                "itc_status": "REVIEW_REQUIRED",
                "eligible_amount": 0.0,
                "ineligible_amount": 0.0,
                "reason": "Item description or context indicates general/retail consumer goods without confirmed business-use or resale context. Manual review required to verify eligibility under Section 16(1).",
                "rule_reference": "CGST Act Sec 16(1) / Sec 17(5)",
            }

        # Default fallback when context is insufficient to determine eligibility definitively
        return {
            "itc_status": "REVIEW_REQUIRED",
            "eligible_amount": 0.0,
            "ineligible_amount": 0.0,
            "reason": "Insufficient specific business context to establish definitive ITC eligibility under Section 16(1). Verification recommended.",
            "rule_reference": "CGST Act Sec 16 / Sec 17(5)",
        }

    def evaluate_itc(
        self,
        invoice_data: Dict[str, Any],
        accounting_output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates invoice-level and line-level Input Tax Credit (ITC) eligibility.
        """
        if not isinstance(invoice_data, dict):
            invoice_data = {}

        data_obj = invoice_data.get("data") if isinstance(invoice_data.get("data"), dict) else invoice_data

        # Check reverse charge
        af = data_obj.get("additional_fields") or {}
        rc_text = str(
            af.get("Whether tax is payable under Reverse Charge?")
            or af.get("reverse_charge")
            or data_obj.get("reverse_charge")
            or ""
        ).lower()
        is_reverse_charge = "yes" in rc_text or rc_text == "true"

        line_items = data_obj.get("line_items") or []
        accounting_lines = (accounting_output or {}).get("accounting") or []

        # Map line-level accounting classifications by index
        acc_by_index: Dict[int, Dict[str, Any]] = {}
        for acc in accounting_lines:
            if isinstance(acc, dict):
                idx = acc.get("line_index")
                if idx is not None:
                    acc_by_index[idx] = acc

        total_tax_amount = 0.0
        total_eligible = 0.0
        total_ineligible = 0.0
        has_review = False
        has_ineligible = False
        line_breakdowns: List[Dict[str, Any]] = []

        # Top-level tax amounts using robust extractors
        from app.services.gst_engine import extract_tax_value, parse_clean_numeric

        header_cgst = extract_tax_value(data_obj, "cgst") or 0.0
        header_sgst = extract_tax_value(data_obj, "sgst") or 0.0
        header_igst = extract_tax_value(data_obj, "igst") or 0.0
        header_cess = extract_tax_value(data_obj, "cess") or 0.0

        if header_cgst > 0 or header_sgst > 0 or header_igst > 0:
            header_tax = round(header_cgst + header_sgst + header_igst + header_cess, 2)
        else:
            header_tax = parse_clean_numeric(data_obj.get("tax_total")) or parse_clean_numeric(data_obj.get("total_tax")) or 0.0

        if line_items:
            # First pass: evaluate line items
            for idx, item in enumerate(line_items, 1):
                if not isinstance(item, dict):
                    continue

                desc = str(item.get("description") or f"Line Item {idx}")
                hsn = str(item.get("hsn_code") or item.get("hsn") or "")

                # Line item tax amount
                l_cgst = float(item.get("cgst_amount") or 0.0)
                l_sgst = float(item.get("sgst_amount") or 0.0)
                l_igst = float(item.get("igst_amount") or 0.0)
                l_tax = round(l_cgst + l_sgst + l_igst, 2)

                # Fallback to rate * taxable if line tax amounts omitted
                if l_tax == 0.0:
                    taxable = float(item.get("taxable_amount") or item.get("total") or 0.0)
                    rate = float(item.get("gst_rate") or item.get("tax_rate") or ((item.get("cgst_rate") or 0.0) + (item.get("sgst_rate") or 0.0) + (item.get("igst_rate") or 0.0)))
                    if taxable > 0 and rate > 0:
                        l_tax = round(taxable * rate / 100.0, 2)

                # Lookup corresponding accounting output
                acc_info = acc_by_index.get(idx) or (acc_by_index.get(idx - 1) if idx - 1 in acc_by_index else {})
                acc_name = acc_info.get("ai_account_name") or acc_info.get("account_name")
                acc_id = acc_info.get("ai_account_id") or acc_info.get("account_id")

                eval_result = self.evaluate_line_itc(
                    description=desc,
                    account_name=acc_name,
                    account_id=acc_id,
                    hsn_code=hsn,
                    tax_amount=l_tax,
                    is_reverse_charge=is_reverse_charge,
                )

                status = eval_result["itc_status"]
                el_amt = eval_result["eligible_amount"]
                inel_amt = eval_result["ineligible_amount"]

                total_tax_amount += l_tax
                total_eligible += el_amt
                total_ineligible += inel_amt

                if status == "INELIGIBLE":
                    has_ineligible = True
                elif status == "REVIEW_REQUIRED":
                    has_review = True

                line_breakdowns.append({
                    "line_index": idx,
                    "description": desc,
                    "account_name": acc_name,
                    "hsn_code": hsn,
                    "tax_amount": l_tax,
                    "itc_status": status,
                    "eligible_amount": el_amt,
                    "ineligible_amount": inel_amt,
                    "reason": eval_result["reason"],
                    "rule_reference": eval_result["rule_reference"],
                })

            # If line-item tax sum is 0 but header tax is present, distribute header tax
            if total_tax_amount == 0.0 and header_tax > 0.0 and len(line_breakdowns) > 0:
                total_tax_amount = header_tax
                # If single line or all lines have same status, allocate header tax
                if len(line_breakdowns) == 1:
                    line = line_breakdowns[0]
                    line["tax_amount"] = header_tax
                    if line["itc_status"] == "ELIGIBLE":
                        line["eligible_amount"] = header_tax
                        total_eligible = header_tax
                    elif line["itc_status"] == "INELIGIBLE":
                        line["ineligible_amount"] = header_tax
                        total_ineligible = header_tax
                else:
                    # Distribute equally or by line presence
                    portion = round(header_tax / len(line_breakdowns), 2)
                    total_eligible = 0.0
                    total_ineligible = 0.0
                    for line in line_breakdowns:
                        line["tax_amount"] = portion
                        if line["itc_status"] == "ELIGIBLE":
                            line["eligible_amount"] = portion
                            total_eligible += portion
                        elif line["itc_status"] == "INELIGIBLE":
                            line["ineligible_amount"] = portion
                            total_ineligible += portion
                    total_eligible = round(total_eligible, 2)
                    total_ineligible = round(total_ineligible, 2)
        else:
            # When no line items are present, evaluate on overall invoice tax total
            invoice_tax = header_tax
            total_tax_amount = invoice_tax

            vendor_desc = str(data_obj.get("vendor_name") or "General Vendor")
            eval_result = self.evaluate_line_itc(
                description=vendor_desc,
                account_name=None,
                account_id=None,
                hsn_code=None,
                tax_amount=invoice_tax,
                is_reverse_charge=is_reverse_charge,
            )

            status = eval_result["itc_status"]
            total_eligible = eval_result["eligible_amount"]
            total_ineligible = eval_result["ineligible_amount"]

            if status == "INELIGIBLE":
                has_ineligible = True
            elif status == "REVIEW_REQUIRED":
                has_review = True

            line_breakdowns.append({
                "line_index": 1,
                "description": vendor_desc,
                "account_name": None,
                "hsn_code": None,
                "tax_amount": invoice_tax,
                "itc_status": status,
                "eligible_amount": total_eligible,
                "ineligible_amount": total_ineligible,
                "reason": eval_result["reason"],
                "rule_reference": eval_result["rule_reference"],
            })

        total_tax_amount = round(total_tax_amount, 2)
        total_eligible = round(total_eligible, 2)
        total_ineligible = round(total_ineligible, 2)

        # Invoice-level Overall ITC Status & Reason
        if has_ineligible and total_eligible > 0:
            overall_status = "REVIEW_REQUIRED"
            overall_reason = f"Partial ITC eligibility: ₹{total_eligible:,.2f} eligible, ₹{total_ineligible:,.2f} blocked under Section 17(5)."
            rule_ref = "CGST Act Sec 16(1) & Sec 17(5)"
        elif has_ineligible and total_eligible == 0:
            overall_status = "INELIGIBLE"
            overall_reason = line_breakdowns[0]["reason"] if line_breakdowns else "Blocked under CGST Act Section 17(5)."
            rule_ref = line_breakdowns[0]["rule_reference"] if line_breakdowns else "CGST Act Sec 17(5)"
        elif has_review:
            overall_status = "REVIEW_REQUIRED"
            overall_reason = "Manual review recommended to confirm business use before claiming credit under Section 16(1)."
            rule_ref = "CGST Act Sec 16 / Sec 17(5)"
        else:
            overall_status = "ELIGIBLE"
            overall_reason = "Full input tax credit eligible for business inputs/services under Section 16(1)."
            rule_ref = "CGST Act Sec 16(1)"

        if is_reverse_charge:
            overall_reason += " (Reverse Charge Supply: Input tax credit claimable after discharging RCM tax in cash)."

        return {
            "status": overall_status,
            "eligible_amount": total_eligible,
            "ineligible_amount": total_ineligible,
            "total_tax_amount": total_tax_amount,
            "is_reverse_charge": is_reverse_charge,
            "reason": overall_reason,
            "rule_reference": rule_ref,
            "line_item_breakdown": line_breakdowns,
        }


itc_engine = ITCEngine()
