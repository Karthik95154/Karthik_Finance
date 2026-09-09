import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.db.models import TaxRate, ZohoConnection
from app.services.master_data_service import master_data_service
from app.services.tds_engine import resolve_tds_tax_details, normalize_statutory_text


@pytest.fixture
def mock_org_tds_taxes():
    """
    Standard suite of active Zoho taxes for tenant with duplicate rates:
    - Multiple 10% taxes: Professional ('Amount Withheld'), Dividend, Other Interest
    - Multiple 2% taxes: Technical Fees, Commission or Brokerage, Contractor (Others)
    - 1% tax: Contractor (Individual/HUF)
    - 0.1% tax: Purchase of Goods
    """
    tenant_id = "test-tenant"
    org_id = "test-org"
    return [
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_PROF_10",
            tax_name="Amount Withheld",
            tax_percentage=10.0,
            tax_type="TDS",
            tax_section="professional_fees",
            is_active=True,
        ),
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_DIV_10",
            tax_name="Dividend",
            tax_percentage=10.0,
            tax_type="TDS",
            tax_section="dividend",
            is_active=True,
        ),
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_INT_10",
            tax_name="Other Interest than securities",
            tax_percentage=10.0,
            tax_type="TDS",
            tax_section="income_other_interest_on_securities_specified_person",
            is_active=True,
        ),
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_TECH_2",
            tax_name="Technical Fees (2%)",
            tax_percentage=2.0,
            tax_type="TDS",
            tax_section="technical_services",
            is_active=True,
        ),
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_COMM_2",
            tax_name="Commission or Brokerage",
            tax_percentage=2.0,
            tax_type="TDS",
            tax_section="commission_or_brokerage",
            is_active=True,
        ),
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_CONT_2",
            tax_name="Payment of contractors for Others",
            tax_percentage=2.0,
            tax_type="TDS",
            tax_section="payment_contractors_and_professionals",
            is_active=True,
        ),
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_CONT_1",
            tax_name="Payment of contractors HUF/Indiv",
            tax_percentage=1.0,
            tax_type="TDS",
            tax_section="contract_payments_individual_or_huf",
            is_active=True,
        ),
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_GOODS_01",
            tax_name="Purchase of goods",
            tax_percentage=0.1,
            tax_type="TDS",
            tax_section="purchase_of_goods",
            is_active=True,
        ),
        TaxRate(
            id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_tax_id="ZOHO_INACTIVE_10",
            tax_name="Old Inactive 10% Tax",
            tax_percentage=10.0,
            tax_type="TDS",
            tax_section="professional_fees",
            is_active=False,
        ),
    ]


@pytest.fixture
def mock_db_with_taxes(mock_org_tds_taxes):
    mock_db = AsyncMock()
    mock_conn = ZohoConnection(id=uuid4(), tenant_id="test-tenant", organization_id="test-org", status="CONNECTED")

    def mock_exec(query):
        q_str = str(query)
        if "zoho_connections" in q_str:
            return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_conn]))))
        # tax_rates query
        return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_org_tds_taxes))))

    mock_db.execute = AsyncMock(side_effect=mock_exec)
    return mock_db


@pytest.mark.asyncio
async def test_case_1_technical_fts_maps_to_technical_fees_2_pct(mock_db_with_taxes):
    """FTS / Cloud Infrastructure at 2.0% must resolve to Technical Fees (2%)."""
    tax_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="Section 393",
        provision="Section 393(1) SI6(iii)D(a)",
        nature_of_payment="Fees for Technical Services (FTS) & Cloud Infrastructure",
        rate=2.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert tax_id == "ZOHO_TECH_2"


@pytest.mark.asyncio
async def test_case_2_professional_services_maps_to_amount_withheld_10_pct(mock_db_with_taxes):
    """Professional Services (legal, consulting) at 10.0% must resolve to Amount Withheld."""
    tax_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="Section 393",
        provision="Section 393(1) SI6(iii)(D)(b) - Fees",
        nature_of_payment="Professional Services & Legal Consulting",
        rate=10.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert tax_id == "ZOHO_PROF_10"


@pytest.mark.asyncio
async def test_case_3_failing_invoice_approved_10_pct_maps_to_amount_withheld(mock_db_with_taxes):
    """
    The failing invoice's exact metadata: Section 393, 10.0% rate, FTS reasoning.
    Even with 'Fees for Technical Services' text, because rate is 10.0%, it matches
    the operational 10% withholding tax ('Amount Withheld') and NOT Dividend/Interest.
    """
    tax_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)] - Professional and Technical Services",
        nature_of_payment="Fees for Technical Services (FTS) & Cloud Infrastructure",
        rate=10.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert tax_id == "ZOHO_PROF_10"


@pytest.mark.asyncio
async def test_case_4_multiple_10_pct_taxes_never_picks_dividend_or_interest_for_vendor(mock_db_with_taxes):
    """Service bills must never map to Dividend or Interest simply because the rate is 10%."""
    # Vendor consultancy bill
    tax_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="194J",
        provision="Section 194J - Professional Services",
        nature_of_payment="Consultancy Fees",
        rate=10.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert tax_id == "ZOHO_PROF_10"
    assert tax_id != "ZOHO_DIV_10"
    assert tax_id != "ZOHO_INT_10"


@pytest.mark.asyncio
async def test_case_5_multiple_2_pct_taxes_differentiates_technical_commission_contractor(mock_db_with_taxes):
    """
    Zoho has 3 active taxes at 2%:
    - Technical Fees (2%)
    - Commission or Brokerage (2%)
    - Payment of contractors for Others (2%)
    Each category must resolve to its own distinct Zoho tax.
    """
    # 1. Technical
    tech_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="Section 393",
        nature_of_payment="Fees for Technical Services (FTS)",
        rate=2.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert tech_id == "ZOHO_TECH_2"

    # 2. Commission
    comm_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="Section 393",
        nature_of_payment="Commission & Brokerage Payments",
        rate=2.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert comm_id == "ZOHO_COMM_2"

    # 3. Contractor
    cont_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="Section 393",
        nature_of_payment="Work Contracts & Sub-contractor Services",
        rate=2.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert cont_id == "ZOHO_CONT_2"


@pytest.mark.asyncio
async def test_case_6_contractor_individual_1_pct_and_goods_0_1_pct(mock_db_with_taxes):
    """Verify 1% contractor and 0.1% purchase of goods mapping."""
    cont_1_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="194C",
        nature_of_payment="Contractor Services (Individual / HUF)",
        rate=1.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert cont_1_id == "ZOHO_CONT_1"

    goods_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="194Q",
        nature_of_payment="Purchase of Goods",
        rate=0.1,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert goods_id == "ZOHO_GOODS_01"


@pytest.mark.asyncio
async def test_case_7_inactive_tax_never_selected(mock_db_with_taxes):
    """ZOHO_INACTIVE_10 is inactive and must never be matched."""
    # When asking for a category where only active taxes should be returned
    tax_id = await master_data_service.get_zoho_tds_tax(
        tenant_id="test-tenant",
        section="Section 393",
        provision="Section 393(1) SI6(iii)(D)(b) - Fees",
        rate=10.0,
        db=mock_db_with_taxes,
        organization_id="test-org",
    )
    assert tax_id != "ZOHO_INACTIVE_10"
    assert tax_id == "ZOHO_PROF_10"


@pytest.mark.asyncio
async def test_case_8_ambiguous_unknown_taxes_safely_fails():
    """
    If multiple active taxes have identical rate and unknown sections with no keywords,
    matcher must return None rather than arbitrarily guessing the first one.
    """
    tenant_id = "test-tenant"
    org_id = "test-org"
    ambiguous_taxes = [
        TaxRate(id=uuid4(), tenant_id=tenant_id, organization_id=org_id, zoho_tax_id="TAX_A", tax_name="Custom Tax Alpha", tax_percentage=5.0, tax_type="TDS", is_active=True),
        TaxRate(id=uuid4(), tenant_id=tenant_id, organization_id=org_id, zoho_tax_id="TAX_B", tax_name="Custom Tax Beta", tax_percentage=5.0, tax_type="TDS", is_active=True),
    ]
    mock_db = AsyncMock()
    mock_conn = ZohoConnection(id=uuid4(), tenant_id=tenant_id, organization_id=org_id, status="CONNECTED")
    def mock_exec(query):
        q_str = str(query)
        if "zoho_connections" in q_str:
            return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_conn]))))
        return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=ambiguous_taxes))))
    mock_db.execute = AsyncMock(side_effect=mock_exec)

    res = await master_data_service.get_zoho_tds_tax(
        tenant_id=tenant_id,
        section="Unknown Section",
        nature_of_payment="General Unspecified",
        rate=5.0,
        db=mock_db,
        organization_id=org_id,
    )
    assert res is None, "Ambiguous taxes without statutory distinguishing metadata must safely return None"


def test_case_9_hitl_approval_preservation_in_effective_tds():
    """
    Finance reviewer explicitly approves 10.0% TDS with Section 393.
    get_effective_tds_data must strictly honor this rate and section, never overwriting it.
    """
    from app.services.tds_engine import get_effective_tds_data
    accounting_payload = {
        "tds_assessment": {
            "tds_applicable": True,
            "approved_tds_rate": 10.0,
            "approved_tds_section": "Section 393",
            "approved_tds_provision": "Section 393(1) SI6(iii)(D)(b) - Fees",
            "approved_nature_of_payment": "Fees for Technical Services (FTS) & Cloud Infrastructure",
            "is_approved": True,
            "tds_base_amount": 50000.0,
        }
    }
    effective = get_effective_tds_data(accounting_payload)
    assert effective["applicable"] is True
    assert effective["rate"] == 10.0
    assert effective["is_approved"] is True
    assert effective["section"] == "Section 393"
    assert effective["tds_amount"] == 5000.0


def test_case_10_statutory_rate_distinction_fts_vs_professional():
    """
    Deterministic statutory classification:
    - FTS & Cloud Infrastructure -> 2.0% (Sl. 6(iii)(D)(a))
    - Professional Services & Legal Consulting -> 10.0% (Sl. 6(iii)(D)(b))
    """
    fts_details = resolve_tds_tax_details(
        section_raw="Section 393",
        provision_raw="Section 393(1) SI6(iii)D(a)",
        nature_raw="Fees for Technical Services (FTS) & Cloud Infrastructure",
        rate_hint=2.0,
    )
    assert fts_details["zoho_section_slug"] == "technical_services"
    assert "6(iii)(D)(a)" in fts_details["provision"]

    prof_details = resolve_tds_tax_details(
        section_raw="Section 393",
        provision_raw="Section 393(1) SI6(iii)(D)(b) - Fees",
        nature_raw="Professional Services & Legal Consulting",
        rate_hint=10.0,
    )
    assert prof_details["zoho_section_slug"] == "professional_fees"
    assert "6(iii)(D)(b)" in prof_details["provision"]
