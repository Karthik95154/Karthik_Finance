"""
Comprehensive Test Suite for Deterministic GST Reverse Charge Mechanism (RCM) Detection.
Verifies compliance with CBIC Notification No. 13/2017-Central Tax (Rate) as amended,
Notification No. 10/2017-Integrated Tax (Rate) as amended, Notification No. 09/2024-CT(R),
and Notification No. 07/2025-CT(R).
"""

import pytest
from app.services.gst_engine import gst_engine


def test_1_legal_service_qualifying_rcm():
    """1. Legal service qualifying for RCM: Advocate/firm to registered business entity -> is_reverse_charge = True"""
    invoice_data = {
        "vendor_name": "Lex Legal & Associates (Advocates)",
        "vendor_gstin": "36AABCL1234A1Z5",
        "customer_name": "Acme Tech Solutions Private Limited",
        "customer_gstin": "36AABCA5678B1Z6",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Legal advisory and representation services before High Court",
                "sac": "998211",
                "taxable_amount": 50000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "LEGAL_SERVICES"
    assert "Notif 13/2017-CT(R) Entry 2" in result["rcm_notification"]
    assert result["rcm_requires_review"] is False


def test_2_legal_service_non_business_recipient_review():
    """2. Legal service where recipient is explicitly an unregistered individual -> not clean RCM, requires review"""
    invoice_data = {
        "vendor_name": "Advocate Sharma",
        "vendor_gstin": "07AAAPS1234P1Z2",
        "customer_name": "John Doe (Individual)",
        "customer_gstin": None,
        "customer_pan": "ABCDE1234P",  # Individual PAN
        "place_of_supply": "07-Delhi",
        "line_items": [
            {
                "description": "Personal family legal dispute consultation",
                "sac": "998211",
                "taxable_amount": 10000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is False
    assert result["rcm_category"] == "LEGAL_SERVICES"
    assert result["rcm_requires_review"] is True
    assert result["validation_status"] == "REVIEW_REQUIRED"


def test_3_security_personnel_qualifying_rcm():
    """3. Security personnel / manned guarding: non-body corporate supplier to registered company -> RCM"""
    invoice_data = {
        "vendor_name": "Suraksha Security Services (Proprietorship)",
        "vendor_pan": "ABCDE1234P",  # Non-body corporate Individual
        "vendor_gstin": "36ABCDE1234P1Z4",
        "customer_name": "Global Corp India Pvt Ltd",
        "customer_pan": "AABCG1234C",  # Body corporate
        "customer_gstin": "36AABCG1234C1Z9",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Supply of security personnel and manned guarding for warehouse",
                "sac": "998525",
                "taxable_amount": 120000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "SECURITY_SERVICES"
    assert "Notif 29/2018-CT(R)" in result["rcm_notification"]


def test_4_security_equipment_cctv_not_rcm():
    """4. Security camera / CCTV equipment purchase -> NOT security manpower RCM"""
    invoice_data = {
        "vendor_name": "HikVision Electronics",
        "vendor_gstin": "29AABCH5678J1Z2",
        "customer_gstin": "29BMDNQ4069K220",
        "place_of_supply": "29-Karnataka",
        "line_items": [
            {
                "description": "CCTV Camera and surveillance security system equipment",
                "hsn": "8525",
                "taxable_amount": 75000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is False
    assert result["rcm_category"] is None
    assert result["rcm_requires_review"] is False


def test_5_director_sitting_fee_rcm():
    """5. Director services to the company -> RCM"""
    invoice_data = {
        "vendor_name": "R. K. Narayanan (Independent Director)",
        "vendor_pan": "ABCDE5678P",
        "customer_name": "Zenith Technologies Pvt Ltd",
        "customer_gstin": "36AAACZ1234K1ZV",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Director sitting fee for attending Q2 Board meetings",
                "sac": "998311",
                "taxable_amount": 100000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "DIRECTOR_SERVICES"
    assert "Notif 13/2017-CT(R) Entry 6" in result["rcm_notification"]


def test_6_employee_salary_not_director_rcm():
    """6. Employee salary / payroll remuneration -> NOT director service RCM (Schedule III, not supply)"""
    invoice_data = {
        "vendor_name": "John Doe",
        "customer_name": "Zenith Technologies Pvt Ltd",
        "customer_gstin": "36AAACZ1234K1ZV",
        "line_items": [
            {
                "description": "Monthly executive employee salary and compensation",
                "taxable_amount": 250000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is False
    assert result["rcm_category"] is None


def test_7_gta_qualifying_case_rcm():
    """7. GTA qualifying case: Goods Transport Agency with consignment note to registered entity -> RCM"""
    invoice_data = {
        "vendor_name": "FastTrack Goods Transport Agency",
        "vendor_gstin": "27AABCF1234M1Z8",
        "customer_name": "Manufacturing Enterprises Pvt Ltd",
        "customer_gstin": "36AABCM5678N1Z2",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Freight charges for road transport with consignment note LR No: 98765",
                "sac": "996511",
                "taxable_amount": 45000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "GTA"
    assert result["supply_type"] == "INTER_STATE"


def test_8_ordinary_road_transport_non_gta():
    """8. Ordinary cab/passenger/courier transport without GTA consignment note -> NOT GTA RCM"""
    invoice_data = {
        "vendor_name": "Local City Courier Services",
        "vendor_gstin": "36AABCC9999K1Z1",
        "customer_gstin": "36AABCM5678N1Z2",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Local office courier document delivery charges",
                "sac": "996812",
                "taxable_amount": 2500.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is False
    assert result["rcm_category"] != "GTA"


def test_9_renting_motor_vehicle_qualifying_rcm():
    """9. Renting motor vehicle with fuel: non-body corporate to body corporate -> RCM"""
    invoice_data = {
        "vendor_name": "Sri Travels (Individual Proprietorship)",
        "vendor_pan": "ABCDE9876P",  # Non-body corporate
        "customer_name": "Enterprise Holdings Private Limited",
        "customer_pan": "AABCE1234C",  # Body corporate
        "customer_gstin": "36AABCE1234C1Z7",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Renting of motor vehicle for monthly executive passenger cab hire with fuel",
                "sac": "996601",
                "taxable_amount": 60000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "RENTING_OF_MOTOR_VEHICLE"
    assert "Notif 22/2019-CT(R)" in result["rcm_notification"]


def test_10_vehicle_purchase_or_repair_not_rcm():
    """10. Vehicle purchase / vehicle repair -> NOT motor vehicle renting RCM"""
    invoice_data = {
        "vendor_name": "Maruti Authorized Service Station",
        "vendor_gstin": "36AABCS1234R1Z3",
        "customer_gstin": "36AABCE1234C1Z7",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Company car repair and scheduled vehicle maintenance",
                "sac": "998714",
                "taxable_amount": 18000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is False
    assert result["rcm_category"] is None


def test_11_foreign_supplier_import_of_service_rcm():
    """11. Overseas supplier import-of-service case: explicit foreign address/country + Indian registered recipient -> RCM"""
    invoice_data = {
        "vendor_name": "Cloud Infra LLC",
        "vendor_country": "USA",
        "vendor_address": "100 Tech Way, San Francisco, California 94105, USA",
        "vendor_gstin": None,
        "customer_name": "Sakshi Tech Pvt Ltd",
        "customer_gstin": "36AABCS1111K1Z2",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Cloud server hosting and SaaS infrastructure services",
                "sac": "998315",
                "taxable_amount": 80000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "IMPORT_OF_SERVICES"
    assert "IGST Act Sec 5(3)" in result["rcm_notification"]


def test_12_foreign_name_alone_not_automatically_rcm():
    """12. Foreign-sounding name or currency alone without explicit overseas location evidence -> NOT RCM"""
    invoice_data = {
        "vendor_name": "Global Tech Ventures",
        "vendor_address": "Plot 45, HITEC City, Hyderabad, Telangana 500081, India",
        "vendor_gstin": "36AABCG7777H1Z5",
        "customer_gstin": "36AABCS1111K1Z2",
        "currency": "USD",  # Foreign currency on domestic billing
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Software consulting services",
                "sac": "998314",
                "taxable_amount": 50000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is False
    assert result["rcm_category"] != "IMPORT_OF_SERVICES"


def test_13_explicit_invoice_rcm_yes_with_matching_conditions():
    """13. Explicit invoice \"RCM = YES\" matching statutory GTA conditions -> clean RCM without conflict"""
    invoice_data = {
        "vendor_name": "National Roadways GTA",
        "vendor_gstin": "27AABCN1234P1Z3",
        "customer_gstin": "36AABCS1111K1Z2",
        "place_of_supply": "36-Telangana",
        "reverse_charge": "Yes",
        "line_items": [
            {
                "description": "Transport of goods in goods carriage with consignment note",
                "sac": "996511",
                "taxable_amount": 30000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "GTA"
    assert result["rcm_conflict"] is None
    assert result["rcm_requires_review"] is False


def test_14_explicit_rcm_yes_conflicting_with_facts():
    """14. Explicit \"RCM = YES\" conflicting with transaction facts (e.g. CCTV purchase) -> is_reverse_charge=False, conflict flagged, requires review"""
    invoice_data = {
        "vendor_name": "Metro Electronics",
        "vendor_gstin": "36AABCM4444N1Z9",
        "customer_gstin": "36AABCS1111K1Z2",
        "place_of_supply": "36-Telangana",
        "reverse_charge": "Yes",  # Conflict!
        "line_items": [
            {
                "description": "Purchase of office laptops and computer monitors",
                "hsn": "8471",
                "taxable_amount": 150000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is False
    assert result["rcm_requires_review"] is True
    assert result["rcm_conflict"] == "EXPLICIT_RCM_CONTRADICTS_FACTS"
    assert result["validation_status"] == "REVIEW_REQUIRED"


def test_15_explicit_rcm_no_overridden_by_statutory_rule():
    """15. Explicit \"RCM = NO\" but statutory advocate legal conditions clearly satisfied -> deterministic RCM wins"""
    invoice_data = {
        "vendor_name": "Advocate Rao & Associates",
        "vendor_gstin": "36AABCR1234A1Z1",
        "customer_name": "Alpha Corp Ltd",
        "customer_gstin": "36AABCA1234B1Z2",
        "place_of_supply": "36-Telangana",
        "reverse_charge": "No",  # Invoice mistakenly printed No
        "line_items": [
            {
                "description": "Legal advisory and court representation by advocate",
                "sac": "998211",
                "taxable_amount": 40000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "LEGAL_SERVICES"
    assert result["rcm_conflict"] == "STATUTORY_RCM_OVERRIDES_INVOICE"


def test_16_ambiguous_rcm_signal_requires_review():
    """16. Ambiguous SAC / service description (e.g. vague \"freight charges\" without GTA facts) -> REVIEW_REQUIRED"""
    invoice_data = {
        "vendor_name": "Speedy Deliveries",
        "vendor_gstin": "36AABCS9999K1Z4",
        "customer_gstin": "36AABCA1234B1Z2",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "General transport and handling charges",
                "taxable_amount": 12000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is False
    assert result["rcm_requires_review"] is True
    assert result["validation_status"] == "REVIEW_REQUIRED"
    assert "Ambiguous transaction facts" in result["rcm_reason"]


def test_17_intra_state_rcm_case():
    """17. Intra-state RCM: Supplier state == POS state -> supply_type = INTRA_STATE and is_reverse_charge = True"""
    invoice_data = {
        "vendor_name": "Advocate K. Sharma",
        "vendor_gstin": "07AAAPS1234P1Z2",  # Delhi (07)
        "customer_name": "Delhi Enterprise Pvt Ltd",
        "customer_gstin": "07AAACD5678K1Z5",  # Delhi (07)
        "place_of_supply": "07-Delhi",
        "line_items": [
            {
                "description": "Advocate legal consultation fees",
                "sac": "998211",
                "taxable_amount": 25000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supply_type"] == "INTRA_STATE"
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "LEGAL_SERVICES"


def test_18_inter_state_rcm_case():
    """18. Inter-state RCM: Supplier state != POS state -> supply_type = INTER_STATE and is_reverse_charge = True"""
    invoice_data = {
        "vendor_name": "Advocate R. Mehta (Mumbai)",
        "vendor_gstin": "27AAAPM1234P1Z8",  # Maharashtra (27)
        "customer_name": "Telangana IT Solutions Pvt Ltd",
        "customer_gstin": "36AABCT9999P1Z3",  # Telangana (36)
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Legal advisory services by senior advocate",
                "sac": "998211",
                "taxable_amount": 75000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supply_type"] == "INTER_STATE"
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "LEGAL_SERVICES"


def test_19_renting_immovable_property_unregistered_supplier_rcm():
    """19. Renting of immovable property other than residential dwelling by unregistered landlord to registered tenant (Notif 09/2024-CT(R) Entry 5AB / Notif 07/2025-CT(R)) -> RCM"""
    invoice_data = {
        "vendor_name": "Shri Ramachandra (Landlord)",
        "vendor_gstin": None,  # Unregistered landlord
        "vendor_pan": "ABCDE1234P",
        "customer_name": "Acme Innovations Private Limited",
        "customer_gstin": "36AABCA5678B1Z6",  # Registered tenant
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Monthly commercial office rent for corporate headquarters",
                "sac": "997212",
                "taxable_amount": 150000.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["is_reverse_charge"] is True
    assert result["rcm_category"] == "RENTING_IMMOVABLE_PROPERTY_NON_RESIDENTIAL"
    assert "Notif 13/2017-CT(R) Entry 5AB" in result["rcm_notification"]
