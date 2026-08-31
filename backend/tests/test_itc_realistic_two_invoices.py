"""
Realistic 2-Invoice Statutory Test Suite for Hardened Input Tax Credit (ITC) Rule Engine.
Tests:
1. Clearly Eligible Business Input (Cloud SaaS Software Subscription under Section 16(1))
2. Clearly Blocked Input (Corporate Passenger Motor Vehicle under Section 17(5)(a))

Validates invoice-level, line-level breakdowns, and strict mathematical reconciliation.
"""

import pytest
from app.services.itc_engine import itc_engine


def test_realistic_business_invoice_itc_eligible():
    """
    Test Invoice 1: Clearly Eligible Business Input.
    - Vendor: AWS Cloud Computing India Pvt Ltd (Valid GSTIN: 27AABCA1234F1Z5, Maharashtra)
    - Buyer: Sakshi Financial Technologies Pvt Ltd (Valid GSTIN: 27AAACS5678K1Z2, Maharashtra)
    - Invoice: INV-AWS-2026-8891
    - Date: 2026-07-15
    - Description: AWS Cloud Infrastructure, Database & Server Hosting Subscription
    - Intra-state Supply: Taxable Rs. 100,000 | CGST 9% (Rs. 9,000) + SGST 9% (Rs. 9,000) = Rs. 18,000 Tax
    """
    invoice_payload = {
        "invoice_number": "INV-AWS-2026-8891",
        "invoice_date": "2026-07-15",
        "vendor_name": "AWS Cloud Computing India Pvt Ltd",
        "vendor_gstin": "27AABCA1234F1Z5",
        "customer_name": "Sakshi Financial Technologies Pvt Ltd",
        "customer_gstin": "27AAACS5678K1Z2",
        "document_type": "TAX_INVOICE",
        "subtotal": 100000.0,
        "cgst_amount": 9000.0,
        "sgst_amount": 9000.0,
        "igst_amount": 0.0,
        "total_amount": 118000.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "AWS Cloud Infrastructure, Database & Server Hosting Subscription for SaaS platform",
                "hsn_code": "998315",
                "taxable_amount": 100000.0,
                "cgst_amount": 9000.0,
                "sgst_amount": 9000.0,
                "igst_amount": 0.0,
                "total_amount": 118000.0,
            }
        ],
    }

    accounting_output = {
        "accounting": [
            {
                "line_index": 1,
                "ai_account_name": "Software & Cloud Hosting Expenses",
                "account_id": "ACC_EXP_CLOUD",
                "business_purpose": "Core cloud server infrastructure for hosting SaaS application",
            }
        ],
        "recipient_business_activity": "Software Product Development & Cloud IT Services",
    }

    # Evaluate directly against current engine instance
    res = itc_engine.evaluate_itc(invoice_payload, accounting_output=accounting_output, claim_date="2026-08-31")

    # Diagnostic console printout
    print("\n" + "=" * 80)
    print("INVOICE 1: REALISTIC ELIGIBLE BUSINESS INPUT")
    print("=" * 80)
    print(f"Invoice Number:  {invoice_payload['invoice_number']}")
    print(f"Description:     {invoice_payload['line_items'][0]['description']}")
    print(f"Input Tax:       Rs. {res['total_tax_amount']:,.2f}")
    print(f"Eligible ITC:    Rs. {res['eligible_itc']:,.2f}")
    print(f"Blocked ITC:     Rs. {res['blocked_itc']:,.2f}")
    print(f"Reversal ITC:    Rs. {res['reversal_itc']:,.2f}")
    print(f"Review Amount:   Rs. {res['review_amount']:,.2f}")
    print(f"Net ITC:         Rs. {res['net_itc_available']:,.2f}")
    print(f"Final Status:    {res['status']}")
    print(f"Reason:          {res['reason']}")
    print(f"Rule Reference:  {res['rule_reference']}")
    print("-" * 80)
    print("LINE-LEVEL OUTPUT:")
    for line in res["line_item_breakdown"]:
        print(f"  line_index:      {line['line_index']}")
        print(f"  description:     {line['description']}")
        print(f"  tax_amount:      Rs. {line['tax_amount']:,.2f}")
        print(f"  itc_status:      {line['itc_status']}")
        print(f"  eligible_amount: Rs. {line['eligible_amount']:,.2f}")
        print(f"  blocked_amount:  Rs. {line['blocked_amount']:,.2f}")
        print(f"  review_amount:   Rs. {line['review_amount']:,.2f}")
        print(f"  reason:          {line['reason']}")
        print(f"  rule_reference:  {line['rule_reference']}")
    print("=" * 80)

    # 1. Invoice-Level Assertions
    assert res["status"] == "ELIGIBLE"
    assert res["total_tax_amount"] == 18000.0
    assert res["eligible_itc"] == 18000.0
    assert res["eligible_amount"] == 18000.0
    assert res["blocked_itc"] == 0.0
    assert res["ineligible_amount"] == 0.0
    assert res["reversal_itc"] == 0.0
    assert res["review_amount"] == 0.0
    assert res["net_itc_available"] == 18000.0
    assert "Section 16(1)" in res["reason"]
    assert "Sec 16(1)" in res["rule_reference"]

    # 2. Line-Level Assertions
    assert len(res["line_item_breakdown"]) == 1
    line1 = res["line_item_breakdown"][0]
    assert line1["line_index"] == 1
    assert line1["itc_status"] == "ELIGIBLE"
    assert line1["tax_amount"] == 18000.0
    assert line1["eligible_amount"] == 18000.0
    assert line1["blocked_amount"] == 0.0
    assert line1["review_amount"] == 0.0
    assert "Sec 16(1)" in line1["rule_reference"]

    # 3. Mathematical Reconciliation & No Double Counting Check
    assert res["total_tax_amount"] == (
        res["eligible_itc"] + res["blocked_itc"] + res["reversal_itc"] + res["review_amount"]
    )
    assert line1["tax_amount"] == (
        line1["eligible_amount"] + line1["blocked_amount"] + line1["reversal_amount"] + line1["review_amount"]
    )


def test_realistic_blocked_invoice_itc_ineligible():
    """
    Test Invoice 2: Clearly Blocked Input (Corporate Passenger Car).
    - Vendor: Landmark Automobiles Pvt Ltd (Valid GSTIN: 27AABCL7890D1ZE, Maharashtra)
    - Buyer: Sakshi Financial Technologies Pvt Ltd (Valid GSTIN: 27AAACS5678K1Z2, Maharashtra)
    - Invoice: INV-AUTO-2026-1044
    - Date: 2026-07-20
    - Description: Honda City 1.5L Petrol Sedan Passenger Motor Vehicle (5 Seater) for Executive Travel
    - Intra-state Supply: Taxable Rs. 1,200,000 | CGST 14% (Rs. 168,000) + SGST 14% (Rs. 168,000) = Rs. 336,000 Tax
    - Statutory Treatment: Blocked under Section 17(5)(a) (seating capacity <= 13 persons, general corporate use).
    """
    invoice_payload = {
        "invoice_number": "INV-AUTO-2026-1044",
        "invoice_date": "2026-07-20",
        "vendor_name": "Landmark Automobiles Pvt Ltd",
        "vendor_gstin": "27AABCL7890D1ZE",
        "customer_name": "Sakshi Financial Technologies Pvt Ltd",
        "customer_gstin": "27AAACS5678K1Z2",
        "document_type": "TAX_INVOICE",
        "subtotal": 1200000.0,
        "cgst_amount": 168000.0,
        "sgst_amount": 168000.0,
        "igst_amount": 0.0,
        "total_amount": 1536000.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Honda City 1.5L Petrol Sedan Passenger Motor Vehicle 5-seater for executive corporate use",
                "hsn_code": "870322",
                "taxable_amount": 1200000.0,
                "cgst_amount": 168000.0,
                "sgst_amount": 168000.0,
                "igst_amount": 0.0,
                "total_amount": 1536000.0,
            }
        ],
    }

    accounting_output = {
        "accounting": [
            {
                "line_index": 1,
                "ai_account_name": "Vehicles - Motor Cars (Asset)",
                "account_id": "ACC_ASSET_VEHICLE",
                "is_capital_good": True,
                "business_purpose": "Corporate car for executive company transportation",
            }
        ],
        "recipient_business_activity": "Software IT Services",
    }

    # Evaluate directly against current engine instance
    res = itc_engine.evaluate_itc(invoice_payload, accounting_output=accounting_output, claim_date="2026-08-31")

    # Diagnostic console printout
    print("\n" + "=" * 80)
    print("INVOICE 2: REALISTIC BLOCKED MOTOR VEHICLE INPUT")
    print("=" * 80)
    print(f"Invoice Number:  {invoice_payload['invoice_number']}")
    print(f"Description:     {invoice_payload['line_items'][0]['description']}")
    print(f"Input Tax:       Rs. {res['total_tax_amount']:,.2f}")
    print(f"Eligible ITC:    Rs. {res['eligible_itc']:,.2f}")
    print(f"Blocked ITC:     Rs. {res['blocked_itc']:,.2f}")
    print(f"Reversal ITC:    Rs. {res['reversal_itc']:,.2f}")
    print(f"Review Amount:   Rs. {res['review_amount']:,.2f}")
    print(f"Net ITC:         Rs. {res['net_itc_available']:,.2f}")
    print(f"Final Status:    {res['status']}")
    print(f"Reason:          {res['reason']}")
    print(f"Rule Reference:  {res['rule_reference']}")
    print("-" * 80)
    print("LINE-LEVEL OUTPUT:")
    for line in res["line_item_breakdown"]:
        print(f"  line_index:      {line['line_index']}")
        print(f"  description:     {line['description']}")
        print(f"  tax_amount:      Rs. {line['tax_amount']:,.2f}")
        print(f"  itc_status:      {line['itc_status']}")
        print(f"  eligible_amount: Rs. {line['eligible_amount']:,.2f}")
        print(f"  blocked_amount:  Rs. {line['blocked_amount']:,.2f}")
        print(f"  review_amount:   Rs. {line['review_amount']:,.2f}")
        print(f"  reason:          {line['reason']}")
        print(f"  rule_reference:  {line['rule_reference']}")
    print("=" * 80)

    # 1. Invoice-Level Assertions
    assert res["status"] == "INELIGIBLE"
    assert res["total_tax_amount"] == 336000.0
    assert res["eligible_itc"] == 0.0
    assert res["eligible_amount"] == 0.0
    assert res["blocked_itc"] == 336000.0
    assert res["ineligible_amount"] == 336000.0
    assert res["reversal_itc"] == 0.0
    assert res["review_amount"] == 0.0
    assert res["net_itc_available"] == 0.0
    assert "Section 17(5)(a)" in res["reason"]
    assert "17(5)(a)" in res["rule_reference"]

    # 2. Line-Level Assertions
    assert len(res["line_item_breakdown"]) == 1
    line1 = res["line_item_breakdown"][0]
    assert line1["line_index"] == 1
    assert line1["itc_status"] == "INELIGIBLE"
    assert line1["tax_amount"] == 336000.0
    assert line1["eligible_amount"] == 0.0
    assert line1["blocked_amount"] == 336000.0
    assert line1["review_amount"] == 0.0
    assert "17(5)(a)" in line1["rule_reference"]

    # 3. Mathematical Reconciliation & No Double Counting Check
    assert res["total_tax_amount"] == (
        res["eligible_itc"] + res["blocked_itc"] + res["reversal_itc"] + res["review_amount"]
    )
    assert line1["tax_amount"] == (
        line1["eligible_amount"] + line1["blocked_amount"] + line1["reversal_amount"] + line1["review_amount"]
    )
