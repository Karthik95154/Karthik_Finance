import pytest
from app.services.itc_engine import itc_engine


def test_01_core_business_software():
    """A. Normal business software -> ELIGIBLE under Sec 16(1)"""
    invoice_data = {
        "document_type": "TAX_INVOICE",
        "line_items": [
            {
                "description": "AWS Cloud Hosting and Server Infrastructure",
                "taxable_amount": 10000.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ],
    }
    accounting_output = {
        "accounting": [
            {
                "line_index": 1,
                "final_account_name": "Software and Cloud Subscriptions",
            }
        ]
    }
    res = itc_engine.evaluate_itc(invoice_data, accounting_output)
    assert res["status"] == "ELIGIBLE"
    assert res["eligible_itc"] == 1800.0
    assert res["blocked_itc"] == 0.0
    assert "Sec 16(1)" in res["rule_reference"]


def test_02_office_supplies_and_hardware():
    """B/C. Office supplies and hardware -> ELIGIBLE"""
    invoice_data = {
        "line_items": [
            {
                "description": "Office stationery, printer paper, and pens",
                "cgst_amount": 100.0,
                "sgst_amount": 100.0,
            },
            {
                "description": "Dell 27-inch LED Monitor Hardware",
                "cgst_amount": 1800.0,
                "sgst_amount": 1800.0,
            }
        ]
    }
    res = itc_engine.evaluate_itc(invoice_data)
    assert res["status"] == "ELIGIBLE"
    assert res["eligible_itc"] == 3800.0


def test_03_passenger_car_blocked_vs_taxi_exception():
    """E/F. Normal passenger car blocked vs taxi business exception"""
    # Normal corporate passenger car -> INELIGIBLE (Sec 17(5)(a))
    car_invoice = {
        "line_items": [
            {
                "description": "Honda City Passenger Car 5 Seater",
                "cgst_amount": 70000.0,
                "sgst_amount": 70000.0,
            }
        ]
    }
    res_car = itc_engine.evaluate_itc(car_invoice)
    assert res_car["status"] == "INELIGIBLE"
    assert res_car["blocked_itc"] == 140000.0
    assert "17(5)(a)" in res_car["rule_reference"]

    # Taxi / Passenger transport operator -> ELIGIBLE (Sec 17(5)(a)(B) exception)
    taxi_invoice = {
        "line_items": [
            {
                "description": "Maruti Dzire vehicle purchase for cab fleet",
                "cgst_amount": 50000.0,
                "sgst_amount": 50000.0,
                "business_purpose": "passenger transport",
            }
        ]
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "recipient_business_activity": "passenger transport service",
            }
        ]
    }
    res_taxi = itc_engine.evaluate_itc(taxi_invoice, accounting)
    assert res_taxi["status"] == "ELIGIBLE"
    assert res_taxi["eligible_itc"] == 100000.0


def test_04_goods_transport_and_driving_school():
    """G/H. Goods transport vehicle and driving school exceptions"""
    # Goods truck
    truck_invoice = {
        "line_items": [
            {
                "description": "Tata Prima 16-Ton Cargo Truck for freight delivery",
                "cgst_amount": 140000.0,
                "sgst_amount": 140000.0,
            }
        ]
    }
    res_truck = itc_engine.evaluate_itc(truck_invoice)
    assert res_truck["status"] == "ELIGIBLE"
    assert res_truck["eligible_itc"] == 280000.0

    # Driving school vehicle
    driving_school_inv = {
        "line_items": [
            {
                "description": "Hyundai i10 vehicle for driving school training",
                "cgst_amount": 40000.0,
                "sgst_amount": 40000.0,
                "business_purpose": "driving training",
            }
        ]
    }
    res_ds = itc_engine.evaluate_itc(driving_school_inv)
    assert res_ds["status"] == "ELIGIBLE"
    assert res_ds["eligible_itc"] == 80000.0


def test_05_hotel_accommodation_business_vs_vacation():
    """I/J/K. Hotel official business travel vs employee vacation vs unknown purpose"""
    # Official business travel -> ELIGIBLE
    hotel_biz = {
        "line_items": [
            {
                "description": "Hotel accommodation in Bangalore for client meeting and project work",
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
                "business_purpose": "client meeting business travel",
            }
        ]
    }
    res_biz = itc_engine.evaluate_itc(hotel_biz)
    assert res_biz["status"] == "ELIGIBLE"
    assert res_biz["eligible_itc"] == 1800.0

    # Vacation stay -> INELIGIBLE (Sec 17(5)(b)(iii))
    hotel_vac = {
        "line_items": [
            {
                "description": "Hotel resort stay for employee family vacation and leisure holiday",
                "cgst_amount": 1500.0,
                "sgst_amount": 1500.0,
                "business_purpose": "vacation holiday",
            }
        ]
    }
    res_vac = itc_engine.evaluate_itc(hotel_vac)
    assert res_vac["status"] == "INELIGIBLE"
    assert res_vac["blocked_itc"] == 3000.0

    # Unknown stay purpose -> REVIEW_REQUIRED
    hotel_unk = {
        "line_items": [
            {
                "description": "Room stay at Grand Hotel",
                "cgst_amount": 500.0,
                "sgst_amount": 500.0,
            }
        ]
    }
    res_unk = itc_engine.evaluate_itc(hotel_unk)
    assert res_unk["status"] == "REVIEW_REQUIRED"
    assert res_unk["review_amount"] == 1000.0


def test_06_food_and_catering_business_exceptions():
    """L/M. Food staff welfare blocked vs outdoor catering input service exception"""
    # Internal food & catering -> INELIGIBLE
    food_inv = {
        "line_items": [
            {
                "description": "Team lunch and buffet food catering",
                "cgst_amount": 300.0,
                "sgst_amount": 300.0,
            }
        ]
    }
    res_food = itc_engine.evaluate_itc(food_inv)
    assert res_food["status"] == "INELIGIBLE"
    assert res_food["blocked_itc"] == 600.0

    # Catering company purchasing sub-catering service -> ELIGIBLE exception
    cat_inv = {
        "line_items": [
            {
                "description": "Inward catering service for corporate banquet client supply",
                "cgst_amount": 2000.0,
                "sgst_amount": 2000.0,
                "further_taxable_supply": True,
            }
        ]
    }
    res_cat = itc_engine.evaluate_itc(cat_inv)
    assert res_cat["status"] == "ELIGIBLE"
    assert res_cat["eligible_itc"] == 4000.0


def test_07_club_membership_and_health_insurance():
    """N/O/P. Club membership strictly blocked vs health insurance under statutory mandate"""
    # Club membership
    club_inv = {
        "line_items": [
            {
                "description": "Annual corporate golf club membership fees",
                "cgst_amount": 5000.0,
                "sgst_amount": 5000.0,
            }
        ]
    }
    res_club = itc_engine.evaluate_itc(club_inv)
    assert res_club["status"] == "INELIGIBLE"
    assert res_club["blocked_itc"] == 10000.0
    assert "17(5)(b)(ii)" in res_club["rule_reference"]

    # Health insurance with statutory legal mandate (Factories Act) -> ELIGIBLE
    insurance_mandate = {
        "line_items": [
            {
                "description": "Group health insurance for factory workers under Factories Act statutory requirement",
                "cgst_amount": 4500.0,
                "sgst_amount": 4500.0,
                "statutory_mandate_present": True,
            }
        ]
    }
    res_ins = itc_engine.evaluate_itc(insurance_mandate)
    assert res_ins["status"] == "ELIGIBLE"
    assert res_ins["eligible_itc"] == 9000.0


def test_08_works_contract_and_plant_machinery_exception():
    """T/U. Works contract for building (blocked) vs plant and machinery (eligible)"""
    # Civil building construction -> INELIGIBLE (Sec 17(5)(c))
    bldg_inv = {
        "line_items": [
            {
                "description": "Civil construction of new administrative office building",
                "cgst_amount": 50000.0,
                "sgst_amount": 50000.0,
            }
        ]
    }
    res_bldg = itc_engine.evaluate_itc(bldg_inv)
    assert res_bldg["status"] == "INELIGIBLE"
    assert res_bldg["blocked_itc"] == 100000.0

    # Plant and machinery installation works contract -> ELIGIBLE
    pnm_inv = {
        "line_items": [
            {
                "description": "Works contract for fabrication and foundation of factory plant and machinery line",
                "cgst_amount": 30000.0,
                "sgst_amount": 30000.0,
            }
        ]
    }
    res_pnm = itc_engine.evaluate_itc(pnm_inv)
    assert res_pnm["status"] == "ELIGIBLE"
    assert res_pnm["eligible_itc"] == 60000.0


def test_09_gifts_free_samples_and_written_off_goods():
    """V/W/X/Y/Z. Section 17(5)(h) gifts, free samples, lost and written-off goods"""
    gift_inv = {
        "line_items": [
            {
                "description": "Corporate gifts and promotional giveaways for festival distribution",
                "cgst_amount": 1000.0,
                "sgst_amount": 1000.0,
            },
            {
                "description": "Damaged goods written off in warehouse inventory",
                "cgst_amount": 2500.0,
                "sgst_amount": 2500.0,
            }
        ]
    }
    res_gift = itc_engine.evaluate_itc(gift_inv)
    assert res_gift["status"] == "INELIGIBLE"
    assert res_gift["blocked_itc"] == 7000.0
    assert "17(5)(h)" in res_gift["rule_reference"]


def test_10_rule_42_common_credit_pro_rata_apportionment():
    """AU/AV. Rule 42 pro-rata reversal on exempt/non-business usage"""
    common_inv = {
        "line_items": [
            {
                "description": "Telecommunication and internet leased line for branch office",
                "cgst_amount": 5000.0,
                "sgst_amount": 5000.0,
                "exempt_use_pct": 20.0,  # 20% used for exempt turnover
            }
        ]
    }
    res = itc_engine.evaluate_itc(common_inv)
    assert res["status"] == "PARTIALLY_ELIGIBLE"
    assert res["total_tax_amount"] == 10000.0
    assert res["reversal_itc"] == 2000.0
    assert res["net_itc_available"] == 8000.0
    assert "Rule 42" in res["rule_reference"]


def test_11_capital_goods_depreciation_restriction():
    """AT. Section 16(3) restriction when depreciation claimed on GST component"""
    cap_inv = {
        "line_items": [
            {
                "description": "Industrial CNC Lathe Machine",
                "cgst_amount": 45000.0,
                "sgst_amount": 45000.0,
            }
        ]
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "is_capital_good": True,
                "depreciation_claimed_on_tax": True,
            }
        ]
    }
    res = itc_engine.evaluate_itc(cap_inv, accounting)
    assert res["status"] == "INELIGIBLE"
    assert res["blocked_itc"] == 90000.0
    assert "16(3)" in res["rule_reference"]


def test_12_invalid_document_type():
    """AM. Bill of supply / Non-GST document -> INELIGIBLE under Rule 36"""
    bos_inv = {
        "document_type": "BILL_OF_SUPPLY",
        "tax_total": 500.0,
        "line_items": [
            {
                "description": "Composition dealer inward supply",
                "cgst_amount": 250.0,
                "sgst_amount": 250.0,
            }
        ]
    }
    res = itc_engine.evaluate_itc(bos_inv)
    assert res["status"] == "INELIGIBLE"
    assert "Rule 36" in res["rule_reference"]


def test_13_gstr2b_matching_and_reversal_state():
    """AN/AO/AQ. GSTR-2B matching and payment reversal lifecycle"""
    inv = {
        "line_items": [
            {
                "description": "Server hosting subscription",
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ]
    }
    # Unmatched / Not available in 2B
    gstr2b_data = {"status": "MATCHED_NOT_AVAILABLE"}
    res_2b = itc_engine.evaluate_itc(inv, gstr2b_data=gstr2b_data)
    assert res_2b["status"] == "REVIEW_REQUIRED"
    assert res_2b["gstr2b_status"] == "MATCHED_NOT_AVAILABLE"

    # Payment pending 180 days
    payment_data = {"status": "PENDING_REVERSAL"}
    res_pay = itc_engine.evaluate_itc(inv, payment_data=payment_data)
    assert res_pay["payment_reversal_status"] == "PENDING_REVERSAL"
    assert any("180 days" in w for w in res_pay["warnings"])
